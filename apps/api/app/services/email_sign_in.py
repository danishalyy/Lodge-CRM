"""Password-proven, browser-bound email sign-in; no code or credential is logged."""

import base64, hashlib, hmac, secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import select, func, update
from ..models import (
    EmailLoginChallenge,
    AccountEmail,
    Membership,
    LodgeGroup,
    Role,
    StaffProfile,
)
from ..security import token_hash, new_token, membership_for
from ..db import set_rls_context
from ..email_service import queue_account_email, validate_email_configuration, _cipher
from ..config import settings

COOKIE = "lodge_login"
TTL = 300
COOLDOWN = 60
MAX_ATTEMPTS = 5
HOURLY_LIMIT = 10


def assert_account_access(db, user):
    """Recheck current identity assignment before issuance and consumption."""
    if not user.is_active:
        raise HTTPException(403, "Account is not activated")
    if user.is_super_admin or user.is_guest:
        return
    set_rls_context(db, None, False, str(user.id))
    memberships = db.scalars(
        select(Membership).where(
            Membership.user_id == user.id, Membership.is_active.is_(True)
        )
    ).all()
    groups = db.scalars(
        select(LodgeGroup).where(
            LodgeGroup.admin_user_id == user.id, LodgeGroup.is_active.is_(True)
        )
    ).all()
    if groups:
        if any(db.get(Role, m.role_id).key != "group_admin" for m in memberships):
            raise HTTPException(403, "Account assignment requires administrator review")
    else:
        if not memberships:
            raise HTTPException(403, "Account access is unavailable")
        if len(memberships) != 1:
            raise HTTPException(
                403, "Account lodge assignment requires administrator review"
            )
        member = memberships[0]
        set_rls_context(db, str(member.lodge_id), False, str(user.id))
        staff = db.scalar(
            select(StaffProfile).where(
                StaffProfile.lodge_id == member.lodge_id,
                StaffProfile.user_id == user.id,
            )
        )
        if staff and staff.employment_status != "active":
            raise HTTPException(403, "Account access is unavailable")
        if not membership_for(db, user, str(member.lodge_id)):
            raise HTTPException(403, "Account access is unavailable")


def credential_digest(user):
    return token_hash(
        f"{user.password_hash}:{user.email}:{user.is_guest}:{user.is_super_admin}"
    )


def code_digest(row, code):
    key = settings.email_encryption_key or settings.mfa_encryption_key
    try:
        material = base64.urlsafe_b64decode(key.encode())
        derived = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"safarios/email-signin/v1",
        ).derive(material)
    except (ValueError, TypeError):
        raise HTTPException(503, "Sign-in email encryption is not configured") from None
    return hmac.new(
        derived, f"{row.id}:{row.user_id}:{code}".encode(), hashlib.sha256
    ).hexdigest()


def cancel_mail(db, ids, user_id):
    if not ids:
        return
    # Bounded transport write after ownership/password verification. The existing
    # outbox RLS remains unchanged; this context never returns operational data.
    set_rls_context(db, None, True, str(user_id))
    try:
        db.execute(
            update(AccountEmail)
            .where(
                AccountEmail.login_challenge_id.in_(ids), AccountEmail.status != "sent"
            )
            .values(status="cancelled", encrypted_payload=None, lease_expires_at=None)
        )
        db.flush()
    finally:
        set_rls_context(db, None, False, str(user_id))


def expire_challenge(db, row, now):
    row.used_at = now
    row.code_hash = None
    cancel_mail(db, [row.id], row.user_id)


def masked_email(email):
    local, domain = email.rsplit("@", 1)
    return local[0] + "•••@" + domain


def issue(db, user, body, request, response, realm):
    validate_email_configuration()
    _cipher()
    now = datetime.now(timezone.utc)
    set_rls_context(db, None, False, str(user.id))
    binding = request.cookies.get(COOKIE) or new_token()
    if body.resend:
        old = db.scalar(
            select(EmailLoginChallenge)
            .where(
                EmailLoginChallenge.token_hash
                == token_hash(body.email_challenge or ""),
                EmailLoginChallenge.user_id == user.id,
            )
            .with_for_update()
        )
        if (
            not old
            or old.realm != realm
            or old.browser_hash != token_hash(binding)
            or old.created_at < now - timedelta(minutes=30)
        ):
            raise HTTPException(401, "Sign in again to request a new email code")
    latest = db.scalar(
        select(EmailLoginChallenge)
        .where(EmailLoginChallenge.user_id == user.id)
        .order_by(EmailLoginChallenge.created_at.desc())
        .limit(1)
    )
    if latest and latest.created_at > now - timedelta(seconds=COOLDOWN):
        seconds = max(
            1,
            int((latest.created_at + timedelta(seconds=COOLDOWN) - now).total_seconds())
            + 1,
        )
        raise HTTPException(
            429,
            "Please wait before requesting another sign-in email",
            headers={"Retry-After": str(seconds)},
        )
    count = db.scalar(
        select(func.count())
        .select_from(EmailLoginChallenge)
        .where(
            EmailLoginChallenge.user_id == user.id,
            EmailLoginChallenge.created_at > now - timedelta(hours=1),
        )
    )
    if count >= HOURLY_LIMIT:
        raise HTTPException(
            429,
            "Too many sign-in emails. Please try again later.",
            headers={"Retry-After": "3600"},
        )
    old_rows = db.scalars(
        select(EmailLoginChallenge)
        .where(
            EmailLoginChallenge.user_id == user.id,
            EmailLoginChallenge.browser_hash == token_hash(binding),
            EmailLoginChallenge.used_at.is_(None),
        )
        .with_for_update()
    ).all()
    for old in old_rows:
        expire_challenge(db, old, now)
    now = datetime.now(timezone.utc)
    raw = new_token()
    code = f"{secrets.randbelow(1000000):06d}"
    row = EmailLoginChallenge(
        user_id=user.id,
        token_hash=token_hash(raw),
        browser_hash=token_hash(binding),
        credential_digest=credential_digest(user),
        realm=realm,
        expires_at=now + timedelta(seconds=TTL),
    )
    db.add(row)
    db.flush()
    row.code_hash = code_digest(row, code)
    set_rls_context(db, None, True, str(user.id))
    try:
        mail = queue_account_email(
            db,
            user=user,
            kind="login_otp",
            title="Your SafariOS sign-in code",
            body=f"Your sign-in code is {code}.\n\nIt expires in 5 minutes and works once in the browser where you entered your password. Never share this code. If you did not request it, ignore this message and secure your account.",
        )
        mail.login_challenge_id = row.id
        db.flush()
    finally:
        set_rls_context(db, None, False, str(user.id))
    db.commit()
    response.status_code = 202
    response.set_cookie(
        COOKIE,
        binding,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=1800,
        path="/",
    )
    return {
        "status": "email_otp_required",
        "challenge_token": raw,
        "masked_email": masked_email(user.email),
        "expires_in": max(
            1, int((row.expires_at - datetime.now(timezone.utc)).total_seconds())
        ),
        "resend_after": COOLDOWN,
    }


def consume(db, user, body, request, realm):
    set_rls_context(db, None, False, str(user.id))
    now = datetime.now(timezone.utc)
    row = db.scalar(
        select(EmailLoginChallenge)
        .where(
            EmailLoginChallenge.token_hash == token_hash(body.email_challenge),
            EmailLoginChallenge.user_id == user.id,
        )
        .with_for_update()
    )
    binding = request.cookies.get(COOKIE, "")
    if (
        not row
        or row.realm != realm
        or not binding
        or not secrets.compare_digest(row.browser_hash, token_hash(binding))
    ):
        raise HTTPException(
            401, "The email code is invalid or expired. Request a new code."
        )
    if (
        row.used_at
        or row.expires_at <= now
        or row.attempts >= MAX_ATTEMPTS
        or row.credential_digest != credential_digest(user)
        or user.is_super_admin
    ):
        expire_challenge(db, row, now)
        db.commit()
        raise HTTPException(
            401, "The email code is invalid or expired. Request a new code."
        )
    if not body.email_code or not secrets.compare_digest(
        row.code_hash or "", code_digest(row, body.email_code)
    ):
        row.attempts += 1
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if row.attempts >= MAX_ATTEMPTS:
            expire_challenge(db, row, now)
        if user.failed_login_count >= 5:
            user.locked_until = now + timedelta(minutes=15)
            user.failed_login_count = 0
        db.commit()
        raise HTTPException(
            401, "The email code is invalid or expired. Request a new code."
        )
    expire_challenge(db, row, now)
    user.email_verified_at = now
    # The caller commits consumption and session creation atomically.


def delivery_valid(db, user, row):
    if (
        not row.login_challenge_id
        or not user
        or user.is_super_admin
        or not user.is_active
    ):
        return False
    challenge = db.get(EmailLoginChallenge, row.login_challenge_id)
    if (
        not challenge
        or challenge.used_at
        or not challenge.code_hash
        or challenge.expires_at <= datetime.now(timezone.utc)
        or challenge.attempts >= MAX_ATTEMPTS
        or challenge.credential_digest != credential_digest(user)
    ):
        return False
    if challenge.realm != ("guest" if user.is_guest else "staff"):
        return False
    try:
        assert_account_access(db, user)
    except HTTPException:
        return False
    return True


def purge_challenges(session_factory, limit=500):
    """Erase expired proofs promptly, retaining only a bounded rate/audit window."""
    from sqlalchemy import delete

    now = datetime.now(timezone.utc)
    with session_factory() as db:
        set_rls_context(db, None, True)
        expired = db.scalars(
            select(EmailLoginChallenge)
            .where(
                EmailLoginChallenge.expires_at <= now,
                EmailLoginChallenge.code_hash.is_not(None),
            )
            .order_by(EmailLoginChallenge.expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for row in expired:
            row.code_hash = None
            row.used_at = row.used_at or now
        ids = [row.id for row in expired]
        if ids:
            db.execute(
                update(AccountEmail)
                .where(
                    AccountEmail.login_challenge_id.in_(ids),
                    AccountEmail.status != "sent",
                )
                .values(
                    status="cancelled", encrypted_payload=None, lease_expires_at=None
                )
            )
        stale = db.scalars(
            select(EmailLoginChallenge.id)
            .where(EmailLoginChallenge.created_at < now - timedelta(hours=24))
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        if stale:
            db.execute(
                delete(EmailLoginChallenge).where(EmailLoginChallenge.id.in_(stale))
            )
        db.commit()
    return {"expired": len(expired), "removed": len(stale)}
