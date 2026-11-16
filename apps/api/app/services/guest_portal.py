"""Guest identity and projections: never grant staff membership or staff RLS scope."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo
from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy import select, text, or_
from sqlalchemy.dialects.postgresql import insert
from ..db import get_db, set_rls_context
from ..models import (
    GuestAccess,
    Guest,
    Stay,
    Lodge,
    Unit,
    User,
    GuestPortalContent,
    GuestRequest,
    GuestNotice,
)
from ..security import (
    _current_user,
    ensure_feature,
    ensure_subscription_read_allowed,
    ensure_subscription_write_allowed,
    entitlement_enabled,
    token_hash,
)


@dataclass
class GuestContext:
    user: User
    access: GuestAccess
    guest: Guest
    stay: Stay
    lodge: Lodge
    cookie: str


def base_context(db, user_id):
    set_rls_context(db, None, False, str(user_id))
    db.execute(text("SELECT set_config('app.guest_mode','true',true)"))


def scope_context(db, access):
    base_context(db, access.user_id)
    for key, value in [
        ("guest_access_id", access.id),
        ("guest_lodge_id", access.lodge_id),
        ("guest_profile_id", access.guest_id),
        ("guest_stay_id", access.stay_id),
    ]:
        db.execute(
            text("SELECT set_config(:key,:value,true)"),
            {"key": "app." + key, "value": str(value)},
        )


def identity(
    request: Request,
    lodge_session: str | None = Cookie(None),
    x_expected_user_id: str | None = Header(None),
    db=Depends(get_db),
):
    user = _current_user(lodge_session, db, x_expected_user_id, persist_activity=False)
    if not user.is_guest or user.is_super_admin:
        raise HTTPException(
            403, "Sign in with your own invited guest account to use the guest portal"
        )
    base_context(db, user.id)
    return user


def validate_access(db, user, access, cookie):
    if not access or access.user_id != user.id or access.revoked_at:
        raise HTTPException(404, "This guest stay is not available to your account")
    scope_context(db, access)
    guest = db.get(Guest, access.guest_id, populate_existing=True)
    stay = db.get(Stay, access.stay_id, populate_existing=True)
    lodge = db.get(Lodge, access.lodge_id, populate_existing=True)
    if (
        not guest
        or guest.anonymized_at
        or not guest.email
        or guest.email.casefold() != user.email.casefold()
        or not stay
        or stay.guest_id != guest.id
        or not lodge
        or lodge.status != "active"
    ):
        raise HTTPException(
            403, "This guest invitation is no longer available. Contact the lodge."
        )
    if stay.status in {"completed", "cancelled"} or datetime.now(
        timezone.utc
    ) >= datetime.combine(
        stay.departure_date + timedelta(days=1), time.min, ZoneInfo(lodge.timezone)
    ):
        raise HTTPException(
            403, "This stay has ended. Contact the lodge if you need assistance."
        )
    ensure_subscription_read_allowed(db, str(lodge.id))
    ensure_feature(db, str(lodge.id), "guest_mobile")
    return GuestContext(user, access, guest, stay, lodge, cookie)


def context(
    access_id: UUID, request: Request, user=Depends(identity), db=Depends(get_db)
):
    row = db.scalar(
        select(GuestAccess).where(
            GuestAccess.id == access_id, GuestAccess.user_id == user.id
        )
    )
    return validate_access(db, user, row, request.cookies.get("lodge_session", ""))


def active_accesses(db, user, cookie):
    base_context(db, user.id)
    rows = db.scalars(
        select(GuestAccess)
        .where(GuestAccess.user_id == user.id, GuestAccess.revoked_at.is_(None))
        .order_by(GuestAccess.created_at.desc())
        .limit(100)
    ).all()
    result = []
    for row in rows:
        try:
            ctx = validate_access(db, user, row, cookie)
            result.append(
                {
                    "id": str(row.id),
                    "lodge_name": ctx.lodge.brand_name or ctx.lodge.name,
                    "arrival_date": ctx.stay.arrival_date.isoformat(),
                    "departure_date": ctx.stay.departure_date.isoformat(),
                }
            )
        except HTTPException as error:
            if error.status_code not in {403, 404}:
                raise
    base_context(db, user.id)
    return result


def published_content(db, ctx):
    now = datetime.now(timezone.utc)
    return db.scalars(
        select(GuestPortalContent)
        .where(
            GuestPortalContent.lodge_id == ctx.lodge.id,
            GuestPortalContent.published.is_(True),
            or_(
                GuestPortalContent.starts_at.is_(None),
                GuestPortalContent.starts_at <= now,
            ),
            or_(GuestPortalContent.ends_at.is_(None), GuestPortalContent.ends_at > now),
        )
        .order_by(GuestPortalContent.position, GuestPortalContent.updated_at.desc())
        .limit(100)
        .execution_options(populate_existing=True)
    ).all()


def content_json(row):
    return {
        "id": str(row.id),
        "kind": row.kind,
        "title": row.title,
        "body": row.body,
        "position": row.position,
        "version": row.version,
        "published": row.published,
        "starts_at": row.starts_at.isoformat() if row.starts_at else None,
        "ends_at": row.ends_at.isoformat() if row.ends_at else None,
    }


def public_request(row):
    # Staff resolution notes, assignees, departments and task IDs are private.
    return {
        "id": str(row.id),
        "request_type": row.request_type,
        "description": row.guest_description or "",
        "status": row.status,
        "created_at": row.created_at.isoformat(),
    }


def request_notice(db, row):
    if not row.guest_access_id:
        return
    access = db.get(GuestAccess, row.guest_access_id)
    if not access or access.revoked_at:
        return
    import uuid
    from sqlalchemy.exc import IntegrityError

    try:
        with db.begin_nested():
            db.execute(
                insert(GuestNotice).values(
                    id=uuid.uuid4(),
                    access_id=access.id,
                    lodge_id=access.lodge_id,
                    user_id=access.user_id,
                    title="Your request has been updated",
                    body="Request status: " + row.status.replace("_", " "),
                    dedupe_key=f"request:{row.id}:{row.status}",
                    created_at=datetime.now(timezone.utc),
                )
            )
    except IntegrityError as error:
        if (
            getattr(error.orig, "sqlstate", None) != "23505"
            or getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            != "uq_guest_notice_dedupe"
        ):
            raise


def notify_staff_of_request(db, ctx, row, request):
    # The guest command has already passed guest-only INSERT RLS. Trusted side
    # effects run in a separate explicitly bounded internal unit of work; this
    # context is never used to read/return a guest response.
    from ..main import audit, event
    from ..notification_service import create_notification, user_ids_with_permission

    set_rls_context(db, str(ctx.lodge.id), False, str(ctx.user.id))
    audit(
        db,
        request,
        ctx.lodge.id,
        ctx.user.id,
        "guest_request.created",
        "guest_request",
        str(row.id),
    )
    event(
        db,
        ctx.lodge.id,
        ctx.user.id,
        "guest_request.created",
        "guest_request",
        str(row.id),
        "Request received from guest portal",
    )
    recipients = user_ids_with_permission(db, ctx.lodge.id, "requests.manage")
    create_notification(
        db,
        lodge_id=ctx.lodge.id,
        notification_type="guest_request.received",
        severity="normal",
        title="Guest request received",
        body="A guest submitted a request. Open guest requests to review it.",
        resource_type="guest_request",
        resource_id=row.id,
        dedupe_key=f"portal-request:{row.id}",
        recipient_user_ids=recipients,
    )
    db.flush()
    # Fire the existing deferred invalidation triggers while the internal writer
    # scope is active, retaining the lodge ordering lock until transaction commit.
    db.execute(
        text(
            "SET CONSTRAINTS trg_live_guest_requests, trg_live_notifications, trg_live_notification_recipients IMMEDIATE"
        )
    )
    db.execute(
        text(
            "SET CONSTRAINTS trg_live_guest_requests, trg_live_notifications, trg_live_notification_recipients DEFERRED"
        )
    )
    scope_context(db, ctx.access)


def invitation_valid(db, user, lodge_id):
    if not lodge_id:
        return False
    for access in db.scalars(
        select(GuestAccess).where(
            GuestAccess.user_id == user.id,
            GuestAccess.lodge_id == lodge_id,
            GuestAccess.revoked_at.is_(None),
        )
    ).all():
        guest = db.get(Guest, access.guest_id)
        stay = db.get(Stay, access.stay_id)
        lodge = db.get(Lodge, lodge_id)
        if (
            guest
            and not guest.anonymized_at
            and guest.email
            and guest.email.casefold() == user.email.casefold()
            and stay
            and stay.status not in {"completed", "cancelled"}
            and lodge
            and lodge.status == "active"
            and datetime.now(timezone.utc)
            < datetime.combine(
                stay.departure_date + timedelta(days=1),
                time.min,
                ZoneInfo(lodge.timezone),
            )
        ):
            return True
    return False
