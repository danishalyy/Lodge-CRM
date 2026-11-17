"""Real two-step sign-in, encrypted delivery, replay/rate/realm and RLS checks."""

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.config import settings
from app.models import EmailLoginChallenge, AccountEmail, AuthSession, User, Membership
from app.email_service import decrypt_payload
from app.security import token_hash


@pytest.fixture
def signin(account, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.fixture.invalid")
    monkeypatch.setattr(settings, "smtp_from_email", "sender@example.com")
    monkeypatch.setattr(settings, "smtp_use_tls", True)
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    account["client"].auto_email_login = False
    account["client"].cookies.clear()
    return account


def begin(a, **extra):
    r = a["client"].post(
        "/api/v1/auth/login",
        json={"email": a["user"].email, "password": a["password"], **extra},
    )
    return r


def issued(a, response):
    assert response.status_code == 202, response.text
    token = response.json()["challenge_token"]
    with a["owner"]() as db:
        row = db.scalar(
            select(EmailLoginChallenge).where(
                EmailLoginChallenge.token_hash == token_hash(token)
            )
        )
        mail = db.scalar(
            select(AccountEmail).where(AccountEmail.login_challenge_id == row.id)
        )
        code = re.search(
            r"code is ([0-9]{6})", decrypt_payload(mail.encrypted_payload)["body"]
        ).group(1)
        return token, code, row.id, mail.id


def verify(a, token, code, **extra):
    return begin(a, email_challenge=token, email_code=code, **extra)


def test_password_only_queues_encrypted_email_without_creating_session(signin):
    a = signin
    with a["owner"]() as db:
        before = db.scalar(select(func.count()).select_from(AuthSession))
    r = begin(a)
    token, code, row_id, mail_id = issued(a, r)
    assert code not in r.text and a["user"].email not in r.text
    assert (
        "lodge_session" not in r.cookies
        and a["client"].get("/api/v1/auth/me").status_code == 401
    )
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    with a["owner"]() as db:
        row = db.get(EmailLoginChallenge, row_id)
        mail = db.get(AccountEmail, mail_id)
        assert (
            row.token_hash != token
            and row.code_hash != code
            and len(row.code_hash) == 64
        )
        assert (
            code not in mail.encrypted_payload
            and a["password"] not in decrypt_payload(mail.encrypted_payload)["body"]
        )
        assert db.scalar(select(func.count()).select_from(AuthSession)) == before
    result = verify(a, token, code)
    assert result.status_code == 200, result.text
    me = a["client"].get("/api/v1/auth/me").json()
    assert me["authentication_method"] == "email_otp" and me["mfa_enabled"]
    assert "lodge_session" in result.cookies and "lodge_csrf" in result.cookies
    with a["owner"]() as db:
        assert (
            db.get(EmailLoginChallenge, row_id).used_at
            and db.get(EmailLoginChallenge, row_id).code_hash is None
        )
        assert db.get(AccountEmail, mail_id).encrypted_payload is None


def test_email_code_cannot_be_replayed_even_with_original_browser_binding(signin):
    a = signin
    token, code, *_ = issued(a, begin(a))
    binding = a["client"].cookies["lodge_login"]
    assert verify(a, token, code).status_code == 200
    a["client"].cookies.clear()
    a["client"].cookies.set("lodge_login", binding)
    assert verify(a, token, code).status_code == 401
    assert a["client"].get("/api/v1/auth/me").status_code == 401


def test_email_code_requires_the_requesting_browser(signin):
    a = signin
    token, code, row_id, _ = issued(a, begin(a))
    binding = a["client"].cookies["lodge_login"]
    a["client"].cookies.clear()
    assert verify(a, token, code).status_code == 401
    with a["owner"]() as db:
        assert db.get(EmailLoginChallenge, row_id).attempts == 0
    a["client"].cookies.set("lodge_login", binding)
    assert verify(a, token, code).status_code == 200


def test_wrong_code_budget_locks_account_and_erases_pending_code(signin):
    a = signin
    token, code, row_id, mail_id = issued(a, begin(a))
    wrong = "000001" if code != "000001" else "000002"
    for _ in range(5):
        assert verify(a, token, wrong).status_code == 401
    assert verify(a, token, code).status_code == 429
    with a["owner"]() as db:
        row = db.get(EmailLoginChallenge, row_id)
        assert row.attempts == 5 and row.used_at and row.code_hash is None
        assert db.get(User, a["user"].id).locked_until > datetime.now(timezone.utc)
        assert db.get(AccountEmail, mail_id).encrypted_payload is None


def test_expired_code_fails_and_erases_delivery_payload(signin):
    a = signin
    token, code, row_id, mail_id = issued(a, begin(a))
    with a["owner"]() as db:
        db.get(EmailLoginChallenge, row_id).expires_at = datetime.now(
            timezone.utc
        ) - timedelta(seconds=1)
        db.commit()
    assert verify(a, token, code).status_code == 401
    with a["owner"]() as db:
        assert db.get(AccountEmail, mail_id).encrypted_payload is None


def test_resend_cooldown_and_invalidated_previous_code(signin):
    a = signin
    token, code, row_id, mail_id = issued(a, begin(a))
    r = begin(a, email_challenge=token, resend=True)
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    with a["owner"]() as db:
        db.get(EmailLoginChallenge, row_id).created_at -= timedelta(seconds=61)
        db.commit()
    new_token, new_code, *_ = issued(a, begin(a, email_challenge=token, resend=True))
    assert token != new_token
    assert verify(a, token, code).status_code == 401
    assert verify(a, new_token, new_code).status_code == 200
    with a["owner"]() as db:
        assert db.get(AccountEmail, mail_id).encrypted_payload is None


def test_hourly_email_cap_cannot_be_bypassed_with_new_browser(signin):
    from app.services.email_sign_in import credential_digest

    a = signin
    with a["owner"]() as db:
        for _ in range(10):
            db.add(
                EmailLoginChallenge(
                    user_id=a["user"].id,
                    token_hash=token_hash(str(uuid4())),
                    browser_hash=token_hash(str(uuid4())),
                    credential_digest=credential_digest(a["user"]),
                    realm="staff",
                    created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
                    expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                )
            )
        db.commit()
    assert begin(a).status_code == 429


@pytest.mark.parametrize("change", ["membership", "password", "email", "inactive"])
def test_account_changes_invalidate_an_issued_code(signin, change):
    from app.security import hash_password

    a = signin
    token, code, *_ = issued(a, begin(a))
    with a["owner"]() as db:
        user = db.get(User, a["user"].id)
        if change == "membership":
            db.scalar(
                select(Membership).where(Membership.user_id == user.id)
            ).is_active = False
        elif change == "password":
            user.password_hash = hash_password("A changed account passphrase 123!")
            a["password"] = "A changed account passphrase 123!"
        elif change == "email":
            user.email = "changed-" + user.email
        else:
            user.is_active = False
        db.commit()
    assert verify(a, token, code).status_code in {401, 403}
    assert a["client"].get("/api/v1/auth/me").status_code == 401


def test_email_delivery_missing_fails_closed(signin, monkeypatch):
    a = signin
    monkeypatch.setattr(settings, "smtp_host", "")
    assert begin(a).status_code == 503
    assert a["client"].get("/api/v1/auth/me").status_code == 401
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(EmailLoginChallenge).where(
                    EmailLoginChallenge.user_id == a["user"].id
                )
            )
            is None
        )


def test_legacy_authenticator_and_recovery_values_do_not_replace_email_code(signin):
    import pyotp
    from app.security import encrypt_mfa_secret

    a = signin
    secret = pyotp.random_base32()
    with a["owner"]() as db:
        user = db.get(User, a["user"].id)
        user.mfa_enabled_at = datetime.now(timezone.utc)
        user.mfa_secret_encrypted = encrypt_mfa_secret(secret)
        db.commit()
    r = begin(a, otp=pyotp.TOTP(secret).now())
    assert r.status_code == 202, r.text
    assert a["client"].get("/api/v1/auth/me").status_code == 401


def test_super_admin_uses_authenticator_and_never_email_code(signin):
    import pyotp
    from app.security import encrypt_mfa_secret

    a = signin
    secret = pyotp.random_base32()
    with a["owner"]() as db:
        user = db.get(User, a["user"].id)
        user.is_super_admin = True
        user.mfa_enabled_at = datetime.now(timezone.utc)
        user.mfa_secret_encrypted = encrypt_mfa_secret(secret)
        db.commit()
    assert begin(a).status_code == 401
    assert begin(a, email_challenge="x" * 32, email_code="123456").status_code == 422
    r = begin(a, otp=pyotp.TOTP(secret).now())
    assert r.status_code == 200, r.text
    assert (
        a["client"].get("/api/v1/auth/me").json()["authentication_method"]
        == "authenticator"
    )
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(EmailLoginChallenge).where(
                    EmailLoginChallenge.user_id == a["user"].id
                )
            )
            is None
        )


def test_enrolment_endpoints_are_super_admin_only(signin):
    a = signin
    token, code, *_ = issued(a, begin(a))
    assert verify(a, token, code).status_code == 200
    headers = {"X-CSRF-Token": a["client"].cookies["lodge_csrf"]}
    for path, body in [
        ("setup", None),
        ("confirm", {"code": "123456"}),
        ("disable", {"code": "123456", "current_password": a["password"]}),
        ("recovery-codes", {"code": "123456", "current_password": a["password"]}),
    ]:
        assert (
            a["client"]
            .post("/api/v1/auth/mfa/" + path, json=body, headers=headers)
            .status_code
            == 403
        )


def test_mail_worker_sends_only_live_codes_and_sanitises_failures(signin, monkeypatch):
    from app import email_jobs

    a = signin
    token, code, row_id, mail_id = issued(a, begin(a))
    sent = []
    monkeypatch.setattr(email_jobs, "send_email", lambda *args: sent.append(args))
    email_jobs.process_account_emails(a["application"])
    assert len(sent) == 1 and code in sent[0][2]
    with a["owner"]() as db:
        assert (
            db.get(AccountEmail, mail_id).status == "sent"
            and db.get(AccountEmail, mail_id).encrypted_payload is None
        )
    assert verify(a, token, code).status_code == 200


def test_expired_mail_is_cancelled_before_smtp(signin, monkeypatch):
    from app import email_jobs

    a = signin
    _, _, row_id, mail_id = issued(a, begin(a))
    with a["owner"]() as db:
        db.get(EmailLoginChallenge, row_id).expires_at = datetime.now(
            timezone.utc
        ) - timedelta(seconds=1)
        db.commit()
    sent = []
    monkeypatch.setattr(email_jobs, "send_email", lambda *args: sent.append(args))
    email_jobs.process_account_emails(a["application"])
    assert sent == []
    with a["owner"]() as db:
        assert (
            db.get(AccountEmail, mail_id).status == "cancelled"
            and db.get(AccountEmail, mail_id).encrypted_payload is None
        )


def test_code_verification_is_consumed_once_under_concurrent_requests(signin):
    from fastapi.testclient import TestClient
    from app.main import app
    from threading import Barrier
    from concurrent.futures import ThreadPoolExecutor

    a = signin
    token, code, *_ = issued(a, begin(a))
    binding = a["client"].cookies["lodge_login"]
    barrier = Barrier(2)

    # Avoid running lifespan production/storage hooks for synthetic API clients.
    def plain_attempt():
        c = TestClient(app)
        try:
            c.cookies.set("lodge_login", binding)
            barrier.wait(timeout=10)
            return c.post(
                "/api/v1/auth/login",
                json={
                    "email": a["user"].email,
                    "password": a["password"],
                    "email_challenge": token,
                    "email_code": code,
                },
            ).status_code
        finally:
            c.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: plain_attempt(), range(2))) == [200, 401]


def test_challenge_rls_has_no_cross_account_or_unscoped_read(signin):
    from app.db import set_rls_context

    a = signin
    _, _, row_id, _ = issued(a, begin(a))
    with a["application"]() as db:
        assert db.scalars(select(EmailLoginChallenge)).all() == []
        set_rls_context(db, None, False, str(uuid4()))
        assert db.scalars(select(EmailLoginChallenge)).all() == []
        set_rls_context(db, None, False, str(a["user"].id))
        assert db.scalar(select(EmailLoginChallenge.id)) == row_id


def test_expired_proofs_are_purged_without_retaining_deliverable_codes(signin):
    from app.services.email_sign_in import purge_challenges

    a = signin
    token, code, row_id, mail_id = issued(a, begin(a))
    with a["owner"]() as db:
        row = db.get(EmailLoginChallenge, row_id)
        row.created_at -= timedelta(hours=25)
        row.expires_at = datetime.now(timezone.utc) - timedelta(hours=24)
        db.commit()
    purged = purge_challenges(a["application"])
    assert purged["expired"] >= 1 and purged["removed"] >= 1
    with a["owner"]() as db:
        assert db.get(EmailLoginChallenge, row_id) is None
        assert db.get(AccountEmail, mail_id).encrypted_payload is None
    assert verify(a, token, code).status_code == 401


def test_security_codes_ignore_notification_email_opt_out(signin):
    a = signin
    with a["owner"]() as db:
        db.get(User, a["user"].id).email_notifications_enabled = False
        db.commit()
    token, code, *_ = issued(a, begin(a))
    assert verify(a, token, code).status_code == 200


# Reuse the real invited guest fixture; it never grants a staff membership.
from test_guest_portal import portal


def test_guest_sign_in_uses_email_code_and_cannot_switch_to_staff_realm(
    portal, monkeypatch
):
    a = portal
    c = a["client"]
    c.auto_email_login = False
    c.cookies.clear()
    monkeypatch.setattr(settings, "smtp_host", "smtp.fixture.invalid")
    monkeypatch.setattr(settings, "smtp_from_email", "sender@example.com")
    body = {"email": a["guest"]["email"], "password": a["guest_password"]}
    r = c.post("/api/v1/guest/auth/login", json=body)
    token, code, *_ = issued(a, r)
    assert c.get(a["portal_path"]).status_code == 401
    assert (
        c.post(
            "/api/v1/auth/login",
            json={**body, "email_challenge": token, "email_code": code},
        ).status_code
        == 401
    )
    r = c.post(
        "/api/v1/guest/auth/login",
        json={**body, "email_challenge": token, "email_code": code},
    )
    assert r.status_code == 200, r.text
    me = c.get("/api/v1/auth/me").json()
    assert (
        me["is_guest"]
        and me["authentication_method"] == "email_otp"
        and not me["memberships"]
    )
    assert c.get(a["portal_path"]).status_code == 200
    assert c.get("/api/v1/platform/lodges").status_code == 403


def test_guest_invitation_is_delivered_without_staff_membership(portal, monkeypatch):
    from test_guest_portal import create_stay
    from app import email_jobs

    a = portal
    monkeypatch.setattr(settings, "smtp_host", "smtp.fixture.invalid")
    monkeypatch.setattr(settings, "smtp_from_email", "sender@example.com")
    guest, stay, invite = create_stay(a)
    assert invite["activation_token"] is None and invite["activation_email_queued"]
    sent = []
    monkeypatch.setattr(email_jobs, "send_email", lambda *args: sent.append(args))
    email_jobs.process_account_emails(a["application"])
    assert any(
        row[0] == guest["email"] and "/activate#token=" in row[2] for row in sent
    )


def test_recovery_invalidates_pending_email_proofs_and_encrypted_delivery(signin):
    from app.ops.post_restore import invalidate_restored_access
    from app.db import set_rls_context

    a = signin
    token, code, row_id, mail_id = issued(a, begin(a))
    with a["application"]() as db:
        set_rls_context(db, None, True)
        invalidate_restored_access(db)
    assert verify(a, token, code).status_code == 401
    with a["owner"]() as db:
        assert db.get(EmailLoginChallenge, row_id).code_hash is None
        assert db.get(AccountEmail, mail_id).encrypted_payload is None


def test_concurrent_resends_issue_only_one_new_code(signin):
    from fastapi.testclient import TestClient
    from app.main import app
    from threading import Barrier
    from concurrent.futures import ThreadPoolExecutor

    a = signin
    token, _, row_id, _ = issued(a, begin(a))
    binding = a["client"].cookies["lodge_login"]
    with a["owner"]() as db:
        db.get(EmailLoginChallenge, row_id).created_at -= timedelta(seconds=61)
        db.commit()
    barrier = Barrier(2)

    def resend():
        c = TestClient(app)
        try:
            c.cookies.set("lodge_login", binding)
            barrier.wait(timeout=10)
            return c.post(
                "/api/v1/auth/login",
                json={
                    "email": a["user"].email,
                    "password": a["password"],
                    "email_challenge": token,
                    "resend": True,
                },
            ).status_code
        finally:
            c.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: resend(), range(2))) == [202, 429]
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(EmailLoginChallenge)
                .where(
                    EmailLoginChallenge.user_id == a["user"].id,
                    EmailLoginChallenge.used_at.is_(None),
                )
            )
            == 1
        )
