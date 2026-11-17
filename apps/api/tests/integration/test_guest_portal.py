"""Real PostgreSQL guest/staff and guest/guest isolation, not UI-only permission checks."""

from datetime import date, timedelta
from uuid import uuid4, UUID
import pytest
from sqlalchemy import select
from app.models import (
    Guest,
    GuestAccess,
    GuestPortalContent,
    GuestRequest,
    User,
    Task,
    Lodge,
    Membership,
    Role,
    GuestNotice,
    Stay,
)
from app.services.guest_portal import scope_context


def staff_client(a):
    a["client"].cookies.clear()
    a["client"].cookies.update(a["staff_cookies"])
    return a["client"]


def create_stay(a, email=None):
    c = staff_client(a)
    base = f"/api/v1/lodges/{a['lodge'].id}"

    def post(path, body):
        r = c.post(base + path, json=body, headers=a["csrf"])
        assert r.status_code == 200, r.text
        return r.json()

    guest = post(
        "/guests",
        {
            "first_name": "Invited",
            "last_name": "Visitor",
            "email": email or uuid4().hex + "@example.com",
            "notes": "STAFF_PROFILE_SECRET",
        },
    )
    room = post("/rooms", {"name": "Guest suite " + uuid4().hex[:8]})
    stay = post(
        "/stays",
        {
            "guest_id": guest["id"],
            "unit_id": room["id"],
            "arrival_date": date.today().isoformat(),
            "departure_date": (date.today() + timedelta(days=2)).isoformat(),
            "special_requirements": "STAFF_STAY_SECRET",
        },
    )
    invitation = post(
        "/guest-portal/guests/" + guest["id"] + "/invite", {"stay_id": stay["id"]}
    )
    return guest, stay, invitation


@pytest.fixture
def portal(account):
    a = account
    a["staff_cookies"] = dict(a["client"].cookies)
    guest, stay, invite = create_stay(a)
    c = a["client"]
    c.cookies.clear()
    password = "Guest private passphrase 123!"
    r = c.post(
        "/api/v1/auth/activate",
        json={"token": invite["activation_token"], "password": password},
    )
    assert r.status_code == 200, r.text
    me = c.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    a.update(
        guest=guest,
        stay=stay,
        invite=invite,
        guest_user=me.json(),
        guest_password=password,
        guest_cookies=dict(c.cookies),
        guest_csrf={"X-CSRF-Token": c.cookies["lodge_csrf"]},
        portal_path="/api/v1/guest/access/" + invite["id"],
    )
    return a


def guest_client(a):
    a["client"].cookies.clear()
    a["client"].cookies.update(a["guest_cookies"])
    return a["client"]


def test_activation_creates_a_guest_principal_without_staff_access(portal):
    a = portal
    c = guest_client(a)
    assert a["guest_user"]["is_guest"] and not a["guest_user"]["memberships"]
    r = c.get(a["portal_path"])
    assert r.status_code == 200, r.text
    assert r.json()["guest_name"] == "Invited"
    assert "STAFF_PROFILE_SECRET" not in r.text and "STAFF_STAY_SECRET" not in r.text
    for path in [
        "/api/v1/platform/lodges",
        f"/api/v1/lodges/{a['lodge'].id}/guests",
        f"/api/v1/lodges/{a['lodge'].id}/tasks",
        "/api/v1/groups",
        "/api/v1/notifications",
    ]:
        assert c.get(path).status_code in {403, 404}, path


def test_staff_and_guest_login_realms_are_separate(portal):
    a = portal
    c = a["client"]
    c.cookies.clear()
    r = c.post(
        "/api/v1/auth/login",
        json={"email": a["guest"]["email"], "password": a["guest_password"]},
    )
    assert r.status_code == 401, r.text
    r = c.post(
        "/api/v1/guest/auth/login",
        json={"email": a["user"].email, "password": a["password"]},
    )
    assert r.status_code == 401, r.text
    r = c.post(
        "/api/v1/guest/auth/login",
        json={"email": a["guest"]["email"], "password": a["guest_password"]},
    )
    assert r.status_code == 200, r.text
    staff_client(a)
    assert c.get(a["portal_path"]).status_code == 403


def test_guest_cannot_read_another_invited_guest_even_in_same_lodge(portal):
    a = portal
    other, stay, invite = create_stay(a)
    c = guest_client(a)
    assert c.get("/api/v1/guest/access/" + invite["id"]).status_code == 404
    assert (
        c.get("/api/v1/guest/access/" + invite["id"] + "/requests").status_code == 404
    )
    r = c.get("/api/v1/guest/accesses")
    assert r.status_code == 200, r.text
    assert [s["id"] for s in r.json()["stays"]] == [a["invite"]["id"]]


def test_guest_sql_context_does_not_open_lodge_wide_rls(portal):
    a = portal
    other, stay, invite = create_stay(a)
    with a["owner"]() as db:
        access = db.get(GuestAccess, UUID(a["invite"]["id"]))
    with a["application"]() as db:
        scope_context(db, access)
        assert [str(g.id) for g in db.scalars(select(Guest)).all()] == [
            a["guest"]["id"]
        ]
        assert [str(s.id) for s in db.scalars(select(Stay)).all()] == [a["stay"]["id"]]
        assert db.scalars(select(Task)).all() == []
        assert [str(u.id) for u in db.scalars(select(User)).all()] == [
            a["guest_user"]["id"]
        ]
        assert [str(l.id) for l in db.scalars(select(Lodge)).all()] == [
            str(a["lodge"].id)
        ]


def test_request_is_owned_idempotent_csrf_protected_and_joins_staff_workflow(
    portal, monkeypatch
):
    a = portal
    c = guest_client(a)
    body = {
        "client_reference": str(uuid4()),
        "request_type": "housekeeping",
        "description": "Please bring fresh towels",
    }
    assert c.post(a["portal_path"] + "/requests", json=body).status_code == 403
    first = c.post(a["portal_path"] + "/requests", json=body, headers=a["guest_csrf"])
    assert first.status_code == 200, first.text
    again = c.post(a["portal_path"] + "/requests", json=body, headers=a["guest_csrf"])
    assert (
        again.status_code == 200 and again.json()["id"] == first.json()["id"]
    ), again.text
    assert (
        c.post(
            a["portal_path"] + "/requests",
            json={**body, "description": "Different command"},
            headers=a["guest_csrf"],
        ).status_code
        == 409
    )
    c = staff_client(a)
    base = f"/api/v1/lodges/{a['lodge'].id}/requests"
    from app.services import guest_portal

    original = guest_portal.request_notice

    def guarded_notice(db, row):
        from sqlalchemy import text

        mode, lodge = db.execute(
            text(
                "SELECT current_setting('app.guest_mode',true),current_setting('app.current_lodge_id',true)"
            )
        ).one()
        assert mode == "false" and lodge == str(row.lodge_id), (
            mode,
            lodge,
            row.lodge_id,
        )
        return original(db, row)

    monkeypatch.setattr(guest_portal, "request_notice", guarded_notice)
    assert any(x["id"] == first.json()["id"] for x in c.get(base).json())
    r = c.patch(
        base + "/" + first.json()["id"],
        json={"status": "in_progress", "description": "STAFF_REQUEST_SECRET"},
        headers=a["csrf"],
    )
    assert r.status_code == 200, r.text
    c = guest_client(a)
    r = c.get(a["portal_path"] + "/requests")
    assert r.status_code == 200, r.text
    assert (
        r.json()[0]["description"] == "Please bring fresh towels"
        and "STAFF_REQUEST_SECRET" not in r.text
    )
    assert r.json()[0]["status"] == "in_progress"
    notes = c.get(a["portal_path"] + "/notifications")
    assert notes.status_code == 200, notes.text
    assert len(notes.json()) == 1 and "STAFF_REQUEST_SECRET" not in notes.text


@pytest.mark.parametrize("state", ["completed", "cancelled"])
def test_stay_completion_or_cancellation_ends_portal_access(portal, state):
    a = portal
    with a["owner"]() as db:
        db.get(Stay, UUID(a["stay"]["id"])).status = state
        db.commit()
    assert guest_client(a).get(a["portal_path"]).status_code == 403
    assert a["client"].get("/api/v1/guest/accesses").json()["stays"] == []


def test_revocation_blocks_existing_session(portal):
    a = portal
    c = staff_client(a)
    r = c.post(
        f"/api/v1/lodges/{a['lodge'].id}/guest-portal/access/{a['invite']['id']}/revoke",
        headers=a["csrf"],
    )
    assert r.status_code == 200, r.text
    assert guest_client(a).get(a["portal_path"]).status_code == 404


def test_guest_reads_only_explicitly_published_information(portal):
    a = portal
    c = staff_client(a)
    base = f"/api/v1/lodges/{a['lodge'].id}/guest-portal/content"
    for published, title in [
        (False, "PRIVATE_DRAFT_SECRET"),
        (True, "Reception contact"),
    ]:
        r = c.post(
            base,
            json={
                "kind": "contact",
                "title": title,
                "body": "Contact reception for help",
                "published": published,
            },
            headers=a["csrf"],
        )
        assert r.status_code == 200, r.text
    r = guest_client(a).get(a["portal_path"])
    assert r.status_code == 200, r.text
    assert "Reception contact" in r.text and "PRIVATE_DRAFT_SECRET" not in r.text


@pytest.fixture
def guest_ai(portal, monkeypatch):
    from app.ai.providers.base import Completion
    from app.services import guest_ai as service

    a = portal
    c = staff_client(a)
    r = c.post(
        f"/api/v1/lodges/{a['lodge'].id}/guest-portal/content",
        json={
            "kind": "contact",
            "title": "Reception",
            "body": "Call reception on extension 100",
            "published": True,
        },
        headers=a["csrf"],
    )
    assert r.status_code == 200, r.text
    a["published"] = r.json()

    class CapturingProvider:
        def __init__(self):
            self.calls = []
            self.change = None

        def complete(self, messages, tools):
            self.calls.append((messages, tools))
            if self.change:
                self.change()
            return Completion("Reception is on extension 100.")

    provider = CapturingProvider()
    monkeypatch.setattr(service, "get_provider", lambda: provider)
    a["provider"] = provider
    return a


def ask_guest(a, question="How do I contact reception?", reference=None):
    return guest_client(a).post(
        a["portal_path"] + "/ai/messages",
        json={"client_reference": reference or str(uuid4()), "content": question},
        headers=a["guest_csrf"],
    )


def test_guest_ai_uses_only_published_content_without_staff_tools_and_is_idempotent(
    guest_ai,
):
    a = guest_ai
    ref = str(uuid4())
    r = ask_guest(a, reference=ref)
    assert r.status_code == 200, r.text
    assert r.json()["answer"] == "Reception is on extension 100."
    assert len(a["provider"].calls) == 1
    messages, tools = a["provider"].calls[0]
    assert tools == []
    assert "extension 100" in str(messages)
    assert "STAFF_PROFILE_SECRET" not in str(
        messages
    ) and "STAFF_STAY_SECRET" not in str(messages)
    again = ask_guest(a, reference=ref)
    assert again.status_code == 200 and again.json()["id"] == r.json()["id"], again.text
    assert len(a["provider"].calls) == 1
    assert ask_guest(a, "A different question?", ref).status_code == 409
    history = guest_client(a).get(a["portal_path"] + "/ai/messages")
    assert history.status_code == 200 and len(history.json()) == 1, history.text
    assert staff_client(a).get(a["portal_path"] + "/ai/messages").status_code == 403
    from app.models import GuestAIMessage
    from app.db import set_rls_context

    with a["application"]() as db:
        set_rls_context(db, str(a["lodge"].id), False, str(a["user"].id))
        assert db.scalars(select(GuestAIMessage)).all() == []
    c = guest_client(a)
    assert c.delete(a["portal_path"] + "/ai/messages").status_code == 403
    assert (
        c.delete(a["portal_path"] + "/ai/messages", headers=a["guest_csrf"]).status_code
        == 200
    )
    assert c.get(a["portal_path"] + "/ai/messages").json() == []


@pytest.mark.parametrize(
    "change", ["revoke", "checkout", "feature", "session", "content", "guest_email"]
)
def test_late_guest_ai_response_cannot_restore_withdrawn_authority_or_sources(
    guest_ai, change
):
    from app.models import AuthSession, LodgeEntitlementOverride, GuestAIMessage
    from datetime import datetime, timezone

    a = guest_ai

    def withdraw():
        with a["owner"]() as db:
            if change == "revoke":
                db.get(GuestAccess, UUID(a["invite"]["id"])).revoked_at = datetime.now(
                    timezone.utc
                )
            elif change == "checkout":
                db.get(Stay, UUID(a["stay"]["id"])).status = "completed"
            elif change == "content":
                db.get(GuestPortalContent, UUID(a["published"]["id"])).published = False
            elif change == "feature":
                db.add(
                    LodgeEntitlementOverride(
                        lodge_id=a["lodge"].id,
                        feature_key="guest_ai",
                        enabled=False,
                        reason="Test-only feature change",
                    )
                )
            elif change == "guest_email":
                db.get(Guest, UUID(a["guest"]["id"])).email = "changed@example.com"
            else:
                for row in db.scalars(
                    select(AuthSession).where(
                        AuthSession.user_id == UUID(a["guest_user"]["id"])
                    )
                ):
                    row.revoked_at = datetime.now(timezone.utc)
            db.commit()

    a["provider"].change = withdraw
    r = ask_guest(a)
    assert r.status_code in {401, 403, 404, 409}, r.text
    assert "extension 100" not in r.text
    with a["owner"]() as db:
        assert (
            db.scalar(
                select(GuestAIMessage).where(
                    GuestAIMessage.access_id == UUID(a["invite"]["id"])
                )
            )
            is None
        )


def test_guest_ai_history_redacts_answers_after_source_unpublish(guest_ai):
    a = guest_ai
    assert ask_guest(a).status_code == 200
    with a["owner"]() as db:
        db.get(GuestPortalContent, UUID(a["published"]["id"])).published = False
        db.commit()
    r = guest_client(a).get(a["portal_path"] + "/ai/messages")
    assert r.status_code == 200, r.text
    assert "extension 100" not in r.text and r.json()[0]["sources"] == []


def test_guest_ai_rejects_tools_without_executing_them(guest_ai):
    from app.ai.providers.base import Completion, ToolCall

    a = guest_ai
    a["provider"].complete = lambda messages, tools: Completion(
        tool_calls=[ToolCall("forbidden", "list_guests", {})]
    )
    assert ask_guest(a).status_code == 503
    assert guest_client(a).get(a["portal_path"] + "/ai/messages").json() == []


@pytest.mark.parametrize("feature", ["guest_mobile", "guest_ai", "guest_requests"])
def test_guest_package_gates_apply_to_snapshot_and_direct_calls(portal, feature):
    from app.models import LodgeEntitlementOverride

    a = portal
    with a["owner"]() as db:
        db.add(
            LodgeEntitlementOverride(
                lodge_id=a["lodge"].id,
                feature_key=feature,
                enabled=False,
                reason="Test gate",
            )
        )
        db.commit()
    c = guest_client(a)
    r = c.get(a["portal_path"])
    if feature == "guest_mobile":
        assert r.status_code == 403
    else:
        assert (
            r.status_code == 200
            and r.json()["features"]["ai" if feature == "guest_ai" else "requests"]
            is False
        )
        assert (
            c.get(
                a["portal_path"]
                + ("/ai/messages" if feature == "guest_ai" else "/requests")
            ).status_code
            == 403
        )


def test_guest_cannot_be_invited_into_staff_membership(portal):
    from sqlalchemy.exc import DBAPIError

    a = portal
    with a["owner"]() as db:
        role = db.scalar(select(Role).where(Role.key == "lodge_admin"))
        db.add(
            Membership(
                user_id=UUID(a["guest_user"]["id"]),
                lodge_id=a["lodge"].id,
                role_id=role.id,
            )
        )
        with pytest.raises(DBAPIError, match="Guests cannot hold internal access"):
            db.commit()


def test_guest_uses_email_verification_and_cannot_enrol_authenticator(portal):
    a = portal
    c = guest_client(a)
    assert c.post("/api/v1/auth/mfa/setup", headers=a["guest_csrf"]).status_code == 403
    me = c.get("/api/v1/auth/me").json()
    assert (
        me["authentication_method"] == "email_otp"
        and me["mfa_enabled"]
        and me["is_guest"]
    )


@pytest.mark.parametrize("state", ["Expired", "Suspended", "Pending"])
def test_guest_subscription_states_preserve_read_only_and_deny_writes(portal, state):
    from app.models import Subscription
    from app.services.clock import lodge_day

    a = portal
    with a["owner"]() as db:
        sub = db.get(Subscription, a["lodge"].id)
        today = lodge_day(db.get(Lodge, a["lodge"].id))
        if state == "Expired":
            sub.expiry_date = today - timedelta(days=1)
            sub.start_date = today - timedelta(days=30)
        elif state == "Suspended":
            sub.suspended = True
        else:
            sub.start_date = today + timedelta(days=1)
        db.commit()
    c = guest_client(a)
    r = c.get(a["portal_path"])
    assert r.status_code == (200 if state == "Expired" else 403), r.text
    if state == "Expired":
        assert r.json()["read_only"]
    r = c.post(
        a["portal_path"] + "/requests",
        json={"client_reference": str(uuid4()), "description": "Please bring towels"},
        headers=a["guest_csrf"],
    )
    assert r.status_code == 403, r.text


def test_guest_information_put_preflight_uses_configured_cors_origin(account):
    from app.config import settings

    r = account["client"].options(
        f"/api/v1/lodges/{account['lodge'].id}/guest-portal/content/{uuid4()}",
        headers={
            "Origin": settings.origins[0],
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "Content-Type,X-CSRF-Token",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers["access-control-allow-origin"] == settings.origins[0]


def test_active_guest_invitation_email_is_encrypted_and_resend_limited(
    portal, monkeypatch
):
    from app.config import settings
    from app.models import AccountEmail

    a = portal
    c = staff_client(a)
    monkeypatch.setattr(settings, "smtp_host", "smtp.fixture.invalid")
    monkeypatch.setattr(settings, "smtp_from_email", "sender@example.com")
    path = (
        f"/api/v1/lodges/{a['lodge'].id}/guest-portal/guests/{a['guest']['id']}/invite"
    )
    r = c.post(path, json={"stay_id": a["stay"]["id"]}, headers=a["csrf"])
    assert r.status_code == 200, r.text
    assert (
        r.json()["delivery_status"] == "pending" and "activation_token" not in r.json()
    )
    assert (
        c.post(path, json={"stay_id": a["stay"]["id"]}, headers=a["csrf"]).status_code
        == 429
    )
    with a["owner"]() as db:
        rows = db.scalars(
            select(AccountEmail).where(
                AccountEmail.user_id == UUID(a["guest_user"]["id"])
            )
        ).all()
        assert (
            len(rows) == 1
            and rows[0].encrypted_payload
            and "/guest?" not in rows[0].encrypted_payload
        )


def test_guest_portal_itinerary_contains_only_own_links_and_no_staff_notes(portal):
    from datetime import datetime, timezone
    from app.models import Activity, ActivityGuest

    a = portal
    other, other_stay, _ = create_stay(a)
    now = datetime.now(timezone.utc)
    with a["owner"]() as db:
        own = Activity(
            lodge_id=a["lodge"].id,
            title="Your own nature walk",
            activity_type="walk",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            requires_vehicle=False,
            notes="PRIVATE_SAFARI_NOTE",
            status="scheduled",
            created_by_user_id=a["user"].id,
        )
        unrelated = Activity(
            lodge_id=a["lodge"].id,
            title="OTHER_GUEST_PRIVATE_SAFARI",
            activity_type="walk",
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            requires_vehicle=False,
            status="scheduled",
            created_by_user_id=a["user"].id,
        )
        db.add_all([own, unrelated])
        db.flush()
        db.add_all(
            [
                ActivityGuest(
                    lodge_id=a["lodge"].id,
                    activity_id=own.id,
                    guest_id=UUID(a["guest"]["id"]),
                ),
                ActivityGuest(
                    lodge_id=a["lodge"].id,
                    activity_id=unrelated.id,
                    guest_id=UUID(other["id"]),
                ),
            ]
        )
        db.commit()
    r = guest_client(a).get(a["portal_path"] + "/itinerary")
    assert r.status_code == 200, r.text
    assert [row["title"] for row in r.json()] == ["Your own nature walk"]
    assert (
        "OTHER_GUEST_PRIVATE_SAFARI" not in r.text
        and "PRIVATE_SAFARI_NOTE" not in r.text
    )


def test_guest_cannot_use_stale_expected_account_header(portal):
    a = portal
    assert (
        guest_client(a)
        .get(a["portal_path"], headers={"X-Expected-User-Id": str(a["user"].id)})
        .status_code
        == 409
    )


@pytest.mark.parametrize(
    "change", ["anonymised", "email_changed", "departure_passed", "lodge_suspended"]
)
def test_guest_identity_and_stay_conditions_rechecked_on_every_request(portal, change):
    from datetime import datetime, timezone

    a = portal
    with a["owner"]() as db:
        if change == "anonymised":
            db.get(Guest, UUID(a["guest"]["id"])).anonymized_at = datetime.now(
                timezone.utc
            )
        elif change == "email_changed":
            db.get(Guest, UUID(a["guest"]["id"])).email = "different@example.com"
        elif change == "departure_passed":
            stay = db.get(Stay, UUID(a["stay"]["id"]))
            stay.arrival_date = date.today() - timedelta(days=5)
            stay.departure_date = date.today() - timedelta(days=3)
        else:
            db.get(Lodge, a["lodge"].id).status = "suspended"
        db.commit()
    assert guest_client(a).get(a["portal_path"]).status_code == 403
    assert a["client"].get("/api/v1/guest/accesses").json()["stays"] == []


def test_guest_notice_acknowledgement_is_owned_and_csrf_protected(portal):
    a = portal
    c = guest_client(a)
    body = {
        "client_reference": str(uuid4()),
        "request_type": "general",
        "description": "Please help with my stay",
    }
    created = c.post(a["portal_path"] + "/requests", json=body, headers=a["guest_csrf"])
    assert created.status_code == 200, created.text
    c = staff_client(a)
    r = c.patch(
        f"/api/v1/lodges/{a['lodge'].id}/requests/{created.json()['id']}",
        json={"status": "in_progress"},
        headers=a["csrf"],
    )
    assert r.status_code == 200, r.text
    c = guest_client(a)
    notice = c.get(a["portal_path"] + "/notifications").json()[0]
    path = a["portal_path"] + "/notifications/" + notice["id"] + "/read"
    assert c.post(path).status_code == 403
    assert c.post(path, headers=a["guest_csrf"]).status_code == 200
    assert c.get(a["portal_path"] + "/notifications").json()[0]["read"] is True
    assert (
        c.post(
            a["portal_path"] + "/notifications/" + str(uuid4()) + "/read",
            headers=a["guest_csrf"],
        ).status_code
        == 404
    )


def test_platform_security_views_do_not_reveal_guest_identity_or_retry_guest_email(
    portal,
):
    from datetime import datetime, timezone
    from app.models import AccountEmail
    from app.security import hash_password
    import pyotp
    from app.security import encrypt_mfa_secret

    a = portal
    with a["owner"]() as db:
        platform = User(
            email=uuid4().hex + "@example.com",
            full_name="Platform operator",
            password_hash=hash_password(a["password"]),
            is_super_admin=True,
            mfa_enabled_at=datetime.now(timezone.utc),
            mfa_secret_encrypted=encrypt_mfa_secret(pyotp.random_base32()),
        )
        db.add(platform)
        db.flush()
        mail = AccountEmail(
            user_id=UUID(a["guest_user"]["id"]),
            lodge_id=a["lodge"].id,
            kind="guest_access",
            destination=a["guest"]["email"],
            status="failed",
            encrypted_payload="TEST-ONLY-NOT-A-REAL-SECRET",
            next_attempt_at=datetime.now(timezone.utc),
        )
        db.add(mail)
        db.commit()
        mail_id = str(mail.id)
    # A synthetic authenticated platform session avoids making this a TOTP timing test.
    from app.models import AuthSession
    from app.security import new_token, token_hash

    cookie, csrf = new_token(), new_token()
    with a["owner"]() as db:
        db.add(
            AuthSession(
                user_id=platform.id,
                token_hash=token_hash(cookie),
                csrf_hash=token_hash(csrf),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()
    c = a["client"]
    c.cookies.clear()
    c.cookies.set("lodge_session", cookie)
    c.cookies.set("lodge_csrf", csrf)
    for path in [
        "/api/v1/platform/users",
        "/api/v1/platform/audit",
        "/api/v1/platform/email",
    ]:
        r = c.get(path)
        assert r.status_code == 200, r.text
        assert a["guest"]["email"] not in r.text and "Invited Visitor" not in r.text
    assert (
        c.post(
            "/api/v1/platform/email/" + mail_id + "/retry",
            headers={"X-CSRF-Token": csrf},
        ).status_code
        == 404
    )


def test_clearing_guest_chat_fences_a_pending_answer_without_restoring_private_history(
    guest_ai,
):
    from app.models import GuestAIMessage
    from app.services.guest_portal import validate_access
    from app.services.guest_ai import clear_history

    a = guest_ai

    def clear_in_other_session():
        with a["owner"]() as owner:
            grant = owner.get(GuestAccess, UUID(a["invite"]["id"]))
        with a["application"]() as db:
            scope_context(db, grant)
            user = db.get(User, UUID(a["guest_user"]["id"]))
            ctx = validate_access(db, user, grant, a["guest_cookies"]["lodge_session"])
            clear_history(db, ctx)

    a["provider"].change = clear_in_other_session
    r = ask_guest(a)
    assert r.status_code == 409, r.text
    assert guest_client(a).get(a["portal_path"] + "/ai/messages").json() == []
    with a["owner"]() as db:
        assert (
            db.scalars(
                select(GuestAIMessage).where(
                    GuestAIMessage.access_id == UUID(a["invite"]["id"]),
                    GuestAIMessage.question != "",
                )
            ).all()
            == []
        )


def test_guest_password_recovery_returns_guest_sign_in_and_revokes_old_sessions(portal):
    from datetime import datetime, timezone
    from app.models import PasswordResetToken
    from app.security import new_token, token_hash

    a = portal
    raw = new_token()
    with a["owner"]() as db:
        db.add(
            PasswordResetToken(
                user_id=UUID(a["guest_user"]["id"]),
                token_hash=token_hash(raw),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
        )
        db.commit()
    c = guest_client(a)
    r = c.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": raw, "password": "New guest passphrase 456!"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sign_in_path"] == "/guest"
    c.cookies.clear()
    c.cookies.update(a["guest_cookies"])
    assert c.get("/api/v1/auth/me").status_code == 401
    c.cookies.clear()
    r = c.post(
        "/api/v1/guest/auth/login",
        json={"email": a["guest"]["email"], "password": "New guest passphrase 456!"},
    )
    assert r.status_code == 200, r.text


def test_guest_revocation_after_an_earlier_clear_still_reports_an_access_denial(
    guest_ai,
):
    from datetime import datetime, timezone

    a = guest_ai
    c = guest_client(a)
    assert (
        c.delete(a["portal_path"] + "/ai/messages", headers=a["guest_csrf"]).status_code
        == 200
    )

    def revoke():
        with a["owner"]() as db:
            db.get(GuestAccess, UUID(a["invite"]["id"])).revoked_at = datetime.now(
                timezone.utc
            )
            db.commit()

    a["provider"].change = revoke
    assert ask_guest(a).status_code == 404
