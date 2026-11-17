"""Separate guest web API. Staff never obtain a guest principal by opening a lodge."""

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field, TypeAdapter, EmailStr, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .db import get_db
from .models import (
    User,
    Guest,
    Stay,
    Lodge,
    Unit,
    GuestAccess,
    GuestPortalContent,
    GuestRequest,
    GuestNotice,
    Activity,
    Transfer,
    AccountEmail,
)
from .schemas import StrictModel, LoginIn
from .security import (
    require_permission,
    require_csrf,
    access_context,
    ensure_feature,
    ensure_subscription_write_allowed,
    entitlement_enabled,
    hash_password,
    new_token,
)
from .email_service import issue_invitation, queue_account_email, email_configured
from .config import settings
from .services.guest_portal import (
    identity,
    context,
    active_accesses,
    published_content,
    public_request,
    content_json,
    notify_staff_of_request,
    scope_context,
)

router = APIRouter()
STAFF = "/api/v1/lodges/{lodge_id}/guest-portal"
GUEST = "/api/v1/guest/access/{access_id}"


class InviteGuest(StrictModel):
    stay_id: UUID


class ContentIn(StrictModel):
    kind: Literal["information", "contact", "service", "announcement", "faq"]
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=4000)
    published: bool = False
    position: int = Field(0, ge=0, le=1000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def dates(self):
        if not self.title.strip() or not self.body.strip():
            raise ValueError("Enter a title and guest information")
        for value in [self.starts_at, self.ends_at]:
            if value and value.tzinfo is None:
                raise ValueError("Announcement times must include a time zone")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("End time must follow start time")
        return self


class RequestIn(StrictModel):
    client_reference: UUID
    request_type: Literal[
        "general", "housekeeping", "maintenance", "food_drink", "transport", "activity"
    ] = "general"
    description: str = Field(min_length=2, max_length=2000)


def manager(db, user, lodge_id):
    ctx = access_context(db, user, lodge_id)
    if ctx.role_key not in {"lodge_admin", "group_admin", "front_office"}:
        raise HTTPException(
            403,
            "Only authorised lodge guest-service managers can manage the guest portal",
        )
    return ctx


@router.post("/api/v1/guest/auth/login")
def guest_login(
    body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)
):
    from .main import login

    return login(body, request, response, db)


@router.get("/api/v1/guest/accesses")
def stays_for_guest(
    request: Request, user=Depends(identity), db: Session = Depends(get_db)
):
    return {
        "user": {
            "id": str(user.id),
            "first_name": user.full_name.split(" ")[0],
            "mfa_enabled": True,
            "authentication_method":"email_otp",
        },
        "stays": active_accesses(db, user, request.cookies.get("lodge_session", "")),
    }


@router.get("/api/v1/lodges/{lodge_id}/guest-portal/guests/{guest_id}")
def guest_access_list(
    lodge_id: str,
    guest_id: UUID,
    user=Depends(require_permission("guest_portal.manage")),
    db: Session = Depends(get_db),
):
    manager(db, user, lodge_id)
    ensure_feature(db, lodge_id, "guests")
    ensure_feature(db, lodge_id, "stays")
    guest = db.scalar(
        select(Guest).where(Guest.id == guest_id, Guest.lodge_id == lodge_id)
    )
    if not guest:
        raise HTTPException(404, "Guest not found")
    grants = db.scalars(
        select(GuestAccess)
        .where(GuestAccess.guest_id == guest.id, GuestAccess.lodge_id == lodge_id)
        .order_by(GuestAccess.created_at.desc())
    ).all()
    return {
        "stays": [
            {
                "id": str(s.id),
                "arrival_date": s.arrival_date.isoformat(),
                "departure_date": s.departure_date.isoformat(),
                "status": s.status,
            }
            for s in db.scalars(
                select(Stay)
                .where(Stay.guest_id == guest.id, Stay.lodge_id == lodge_id)
                .order_by(Stay.arrival_date.desc())
                .limit(100)
            ).all()
        ],
        "accesses": [
            {
                "id": str(g.id),
                "stay_id": str(g.stay_id),
                "revoked": bool(g.revoked_at),
                "account_active": bool(db.get(User, g.user_id).is_active),
                "portal_url": settings.public_web_url.rstrip("/")
                + "/guest?access="
                + str(g.id),
            }
            for g in grants
        ],
    }


@router.post(
    "/api/v1/lodges/{lodge_id}/guest-portal/guests/{guest_id}/invite",
    dependencies=[Depends(require_csrf)],
)
def invite_guest(
    lodge_id: str,
    guest_id: UUID,
    body: InviteGuest,
    request: Request,
    user=Depends(require_permission("guest_portal.manage", write=True)),
    db: Session = Depends(get_db),
):
    manager(db, user, lodge_id)
    ensure_feature(db, lodge_id, "guests")
    ensure_feature(db, lodge_id, "stays")
    guest = db.scalar(
        select(Guest)
        .where(Guest.id == guest_id, Guest.lodge_id == lodge_id)
        .with_for_update()
    )
    if not guest or guest.anonymized_at:
        raise HTTPException(404, "Guest not found or anonymised")
    try:
        email = str(TypeAdapter(EmailStr).validate_python(guest.email)).lower()
    except (ValueError, TypeError):
        raise HTTPException(
            422, "Add a valid email address to this guest before sending an invitation"
        )
    stay = db.scalar(
        select(Stay)
        .where(
            Stay.id == body.stay_id,
            Stay.guest_id == guest.id,
            Stay.lodge_id == lodge_id,
        )
        .with_for_update()
    )
    from .services.clock import lodge_day

    lodge = db.get(Lodge, lodge_id)
    if (
        not stay
        or stay.status in {"completed", "cancelled"}
        or stay.departure_date < lodge_day(lodge)
    ):
        raise HTTPException(409, "Choose an upcoming or current stay for this guest")
    target = db.scalar(select(User).where(User.email == email).with_for_update())
    if target and (not target.is_guest or target.is_super_admin):
        raise HTTPException(
            409,
            "This email already belongs to another account type. Use a separate guest email address.",
        )
    if not target:
        target = User(
            email=email,
            full_name=(guest.first_name + " " + guest.last_name).strip(),
            password_hash=hash_password(new_token() + new_token()),
            is_active=False,
            is_guest=True,
        )
        db.add(target)
        db.flush()
    access = db.scalar(
        select(GuestAccess).where(
            GuestAccess.stay_id == stay.id, GuestAccess.user_id == target.id
        )
    )
    for previous in db.scalars(
        select(GuestAccess).where(
            GuestAccess.stay_id == stay.id,
            GuestAccess.user_id != target.id,
            GuestAccess.revoked_at.is_(None),
        )
    ).all():
        previous.revoked_at = datetime.now(timezone.utc)
    if not access:
        access = GuestAccess(
            lodge_id=lodge.id,
            stay_id=stay.id,
            guest_id=guest.id,
            user_id=target.id,
            created_by_user_id=user.id,
        )
        db.add(access)
    else:
        access.revoked_at = None
    db.flush()
    portal_url = settings.public_web_url.rstrip("/") + "/guest?access=" + str(access.id)
    if not target.is_active:
        result = issue_invitation(db, target, lodge=lodge, creator_id=user.id)
    else:
        result = {"delivery_status": "ready"}
        if email_configured():
            latest = db.scalar(
                select(AccountEmail)
                .where(
                    AccountEmail.user_id == target.id,
                    AccountEmail.lodge_id == lodge.id,
                    AccountEmail.kind == "guest_access",
                )
                .order_by(AccountEmail.created_at.desc())
                .limit(1)
            )
            if latest and latest.created_at > datetime.now(timezone.utc) - timedelta(
                seconds=settings.invitation_resend_cooldown_seconds
            ):
                raise HTTPException(
                    429,
                    "A guest sign-in email was recently sent. Please wait before sending another.",
                )
            queue_account_email(
                db,
                user=target,
                kind="guest_access",
                title="Your lodge guest portal is ready",
                body="Sign in with your own guest account to view this stay and contact your lodge.",
                action_label="Open my stay",
                action_url=portal_url,
                created_by_user_id=user.id,
                lodge_id=lodge.id,
            )
            result["delivery_status"] = "pending"
    from .main import audit

    audit(
        db, request, lodge.id, user.id, "guest_portal.invited", "guest", str(guest.id)
    )
    db.commit()
    return {"id": str(access.id), "portal_url": portal_url, **result}


@router.post(
    "/api/v1/lodges/{lodge_id}/guest-portal/access/{record_id}/revoke",
    dependencies=[Depends(require_csrf)],
)
def revoke_guest(
    lodge_id: str,
    record_id: UUID,
    request: Request,
    user=Depends(require_permission("guest_portal.manage", write=True)),
    db: Session = Depends(get_db),
):
    manager(db, user, lodge_id)
    row = db.scalar(
        select(GuestAccess)
        .where(GuestAccess.id == record_id, GuestAccess.lodge_id == lodge_id)
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Guest access not found")
    row.revoked_at = datetime.now(timezone.utc)
    from .main import audit

    audit(
        db,
        request,
        lodge_id,
        user.id,
        "guest_portal.revoked",
        "guest",
        str(row.guest_id),
    )
    db.commit()
    return {"ok": True}


@router.get("/api/v1/lodges/{lodge_id}/guest-portal/content")
def content_for_staff(
    lodge_id: str,
    user=Depends(require_permission("guest_portal.manage")),
    db: Session = Depends(get_db),
):
    manager(db, user, lodge_id)
    return [
        content_json(row)
        for row in db.scalars(
            select(GuestPortalContent)
            .where(GuestPortalContent.lodge_id == lodge_id)
            .order_by(GuestPortalContent.position, GuestPortalContent.updated_at.desc())
        ).all()
    ]


@router.post(
    "/api/v1/lodges/{lodge_id}/guest-portal/content",
    dependencies=[Depends(require_csrf)],
)
def publish_content(
    lodge_id: str,
    body: ContentIn,
    request: Request,
    user=Depends(require_permission("guest_portal.manage", write=True)),
    db: Session = Depends(get_db),
):
    manager(db, user, lodge_id)
    row = GuestPortalContent(
        lodge_id=lodge_id, updated_by_user_id=user.id, **body.model_dump()
    )
    db.add(row)
    db.flush()
    from .main import audit

    audit(
        db,
        request,
        lodge_id,
        user.id,
        "guest_content.created",
        "guest_content",
        str(row.id),
    )
    db.commit()
    return content_json(row)


@router.put(
    "/api/v1/lodges/{lodge_id}/guest-portal/content/{record_id}",
    dependencies=[Depends(require_csrf)],
)
def update_content(
    lodge_id: str,
    record_id: UUID,
    body: ContentIn,
    request: Request,
    user=Depends(require_permission("guest_portal.manage", write=True)),
    db: Session = Depends(get_db),
):
    manager(db, user, lodge_id)
    row = db.scalar(
        select(GuestPortalContent)
        .where(
            GuestPortalContent.id == record_id, GuestPortalContent.lodge_id == lodge_id
        )
        .with_for_update()
    )
    if not row:
        raise HTTPException(404, "Guest information not found")
    for key, value in body.model_dump().items():
        setattr(row, key, value)
    row.version += 1
    row.updated_by_user_id = user.id
    from .main import audit

    audit(
        db,
        request,
        lodge_id,
        user.id,
        "guest_content.updated",
        "guest_content",
        str(row.id),
    )
    db.commit()
    return content_json(row)


@router.get("/api/v1/guest/access/{access_id}")
def portal_snapshot(ctx=Depends(context), db: Session = Depends(get_db)):
    from .security import subscription_state
    from .ai.configuration import configuration_state

    ctx.stay  # The validated stay is the only source of scope; never a browser lodge/guest ID.
    unit = db.get(Unit, ctx.stay.unit_id)
    features = {
        key: entitlement_enabled(db, str(ctx.lodge.id), feature)
        for key, feature in [
            ("requests", "guest_requests"),
            ("notifications", "notifications"),
            ("activities", "activities"),
            ("transfers", "transfers"),
            ("ai", "guest_ai"),
        ]
    }
    return {
        "access_id": str(ctx.access.id),
        "user_id": str(ctx.user.id),
        "guest_name": ctx.guest.first_name,
        "lodge": {
            "name": ctx.lodge.brand_name or ctx.lodge.name,
            "timezone": ctx.lodge.timezone,
            "date_format": ctx.lodge.date_format,
            "has_logo": bool(ctx.lodge.logo_png),
        },
        "stay": {
            "arrival_date": ctx.stay.arrival_date.isoformat(),
            "departure_date": ctx.stay.departure_date.isoformat(),
            "party_size": ctx.stay.party_size,
            "room": unit.name if unit else None,
        },
        "content": [content_json(row) for row in published_content(db, ctx)],
        "features": features,
        "read_only": subscription_state(db, str(ctx.lodge.id))[1] == "Expired",
        "ai_configured": configuration_state() in {"configured", "test_only"},
    }


@router.get("/api/v1/guest/access/{access_id}/logo")
def guest_logo(ctx=Depends(context)):
    if not ctx.lodge.logo_png:
        raise HTTPException(404, "No lodge logo configured")
    return Response(
        content=ctx.lodge.logo_png,
        media_type="image/png",
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/api/v1/guest/access/{access_id}/itinerary")
def itinerary(ctx=Depends(context), db: Session = Depends(get_db)):
    result = []
    if entitlement_enabled(db, str(ctx.lodge.id), "activities"):
        result += [
            {
                "id": str(row.id),
                "kind": "activity",
                "title": row.title,
                "starts_at": row.starts_at.isoformat(),
                "ends_at": row.ends_at.isoformat(),
                "location": row.meeting_point,
                "status": row.status,
            }
            for row in db.scalars(
                select(Activity)
                .where(
                    Activity.lodge_id == ctx.lodge.id, Activity.status != "cancelled"
                )
                .order_by(Activity.starts_at)
            ).all()
        ]
    if entitlement_enabled(db, str(ctx.lodge.id), "transfers"):
        result += [
            {
                "id": str(row.id),
                "kind": "transfer",
                "title": row.pickup_location + " → " + row.dropoff_location,
                "starts_at": row.scheduled_at.isoformat(),
                "ends_at": row.expected_end_at.isoformat(),
                "location": row.pickup_location,
                "status": row.status,
            }
            for row in db.scalars(
                select(Transfer)
                .where(
                    Transfer.lodge_id == ctx.lodge.id, Transfer.status != "cancelled"
                )
                .order_by(Transfer.scheduled_at)
            ).all()
        ]
    return sorted(result, key=lambda row: row["starts_at"])


@router.get("/api/v1/guest/access/{access_id}/requests")
def own_requests(ctx=Depends(context), db: Session = Depends(get_db)):
    ensure_feature(db, str(ctx.lodge.id), "guest_requests")
    return [
        public_request(row)
        for row in db.scalars(
            select(GuestRequest)
            .where(
                GuestRequest.guest_access_id == ctx.access.id,
                GuestRequest.created_by_user_id == ctx.user.id,
            )
            .order_by(GuestRequest.created_at.desc())
            .limit(100)
        ).all()
    ]


@router.post(
    "/api/v1/guest/access/{access_id}/requests", dependencies=[Depends(require_csrf)]
)
def submit_request(
    body: RequestIn,
    request: Request,
    ctx=Depends(context),
    db: Session = Depends(get_db),
):
    ensure_feature(db, str(ctx.lodge.id), "guest_requests")
    ensure_subscription_write_allowed(db, str(ctx.lodge.id))
    if not body.description.strip():
        raise HTTPException(422, "Describe how the lodge can help")
    previous = db.scalar(
        select(GuestRequest).where(
            GuestRequest.guest_access_id == ctx.access.id,
            GuestRequest.client_reference == body.client_reference,
        )
    )
    if previous:
        if (
            previous.guest_description != body.description.strip()
            or previous.request_type != body.request_type
        ):
            raise HTTPException(
                409,
                "This submission reference has already been used for a different request",
            )
        return public_request(previous)
    from .main import rate_limit_login
    from .services.state import lock_resources

    lock_resources(db, ctx.lodge.id, ("guest-request", body.client_reference))
    # Recheck after the transaction lock for two identical concurrent submissions.
    previous = db.scalar(
        select(GuestRequest).where(
            GuestRequest.guest_access_id == ctx.access.id,
            GuestRequest.client_reference == body.client_reference,
        )
    )
    if previous:
        if (
            previous.guest_description != body.description.strip()
            or previous.request_type != body.request_type
        ):
            raise HTTPException(409, "This submission reference has already been used")
        return public_request(previous)
    rate_limit_login(request, "guest-request:" + str(ctx.user.id))
    row = GuestRequest(
        lodge_id=ctx.lodge.id,
        guest_id=ctx.guest.id,
        stay_id=ctx.stay.id,
        guest_access_id=ctx.access.id,
        client_reference=body.client_reference,
        request_type=body.request_type,
        description=body.description.strip(),
        guest_description=body.description.strip(),
        priority="normal",
        status="open",
        created_by_user_id=ctx.user.id,
    )
    db.add(row)
    db.flush()
    result = public_request(row)
    notify_staff_of_request(db, ctx, row, request)
    db.commit()
    return result


@router.get("/api/v1/guest/access/{access_id}/notifications")
def guest_notifications(ctx=Depends(context), db: Session = Depends(get_db)):
    ensure_feature(db, str(ctx.lodge.id), "notifications")
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "body": row.body,
            "read": bool(row.read_at),
            "created_at": row.created_at.isoformat(),
        }
        for row in db.scalars(
            select(GuestNotice)
            .where(
                GuestNotice.access_id == ctx.access.id,
                GuestNotice.user_id == ctx.user.id,
            )
            .order_by(GuestNotice.created_at.desc())
            .limit(100)
        ).all()
    ]


@router.post(
    "/api/v1/guest/access/{access_id}/notifications/{record_id}/read",
    dependencies=[Depends(require_csrf)],
)
def read_guest_notice(
    record_id: UUID, ctx=Depends(context), db: Session = Depends(get_db)
):
    ensure_feature(db, str(ctx.lodge.id), "notifications")
    row = db.scalar(
        select(GuestNotice).where(
            GuestNotice.id == record_id,
            GuestNotice.access_id == ctx.access.id,
            GuestNotice.user_id == ctx.user.id,
        )
    )
    if not row:
        raise HTTPException(404, "Notification not found")
    row.read_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


class GuestQuestion(StrictModel):
    client_reference: UUID
    content: str = Field(min_length=2, max_length=2000)


@router.get("/api/v1/guest/access/{access_id}/ai/messages")
def guest_chat_history(ctx=Depends(context), db: Session = Depends(get_db)):
    from .services.guest_ai import history

    return history(db, ctx)


@router.post(
    "/api/v1/guest/access/{access_id}/ai/messages", dependencies=[Depends(require_csrf)]
)
def guest_chat(
    body: GuestQuestion,
    request: Request,
    ctx=Depends(context),
    db: Session = Depends(get_db),
):
    from .services.guest_ai import ask
    from .ai.providers.base import ProviderUnavailable

    if not body.content.strip():
        raise HTTPException(422, "Enter a question for the guest assistant")
    try:
        return ask(db, ctx, body.client_reference, body.content.strip(), request)
    except ProviderUnavailable:
        raise HTTPException(
            503, "The guest assistant is not configured. Please contact reception."
        ) from None


@router.delete(
    "/api/v1/guest/access/{access_id}/ai/messages", dependencies=[Depends(require_csrf)]
)
def delete_guest_chat(ctx=Depends(context), db: Session = Depends(get_db)):
    from .services.guest_ai import clear_history

    return clear_history(db, ctx)
