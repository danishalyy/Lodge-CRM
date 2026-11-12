"""Device opt-in and own-user browser notification preferences."""

import hashlib
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from .db import get_db, set_rls_context
from .models import PushSubscription, PushPreference, AuthSession, AuditLog
from .security import (
    require_permission,
    require_csrf,
    token_hash,
    ensure_feature,
    current_user,
)
from . import push_service as service

router = APIRouter()


class Categories(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_assigned: bool = True
    request: bool = True
    overdue: bool = True
    arrival: bool = True


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    categories: Categories


class Keys(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class Device(BaseModel):
    model_config = ConfigDict(extra="forbid")
    endpoint: str = Field(max_length=2048)
    keys: Keys


class RemoveDevice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID
    lodge_id: uuid.UUID


def audit(db, request, user, lodge_id, action):
    db.add(
        AuditLog(
            lodge_id=uuid.UUID(lodge_id),
            actor_user_id=user.id,
            action=action,
            resource_type="browser_push",
            resource_id=str(user.id),
            request_id=request.headers.get("x-request-id", ""),
        )
    )


@router.get("/api/v1/lodges/{lodge_id}/push/preferences")
def push_preferences(
    lodge_id: str,
    request: Request,
    user=Depends(require_permission("notifications.view")),
    db=Depends(get_db),
):
    ensure_feature(db, lodge_id, "notifications")
    pref = db.get(PushPreference, (uuid.UUID(lodge_id), user.id))
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash
            == token_hash(request.cookies.get("lodge_session", "")),
            AuthSession.user_id == user.id,
        )
    )
    bindings = (
        list(
            db.scalars(
                select(PushSubscription.id).where(
                    PushSubscription.lodge_id == lodge_id,
                    PushSubscription.user_id == user.id,
                    PushSubscription.session_id == session.id,
                )
            ).all()
        )
        if session
        else []
    )
    return {
        "bindings": [str(key) for key in bindings],
        "configured": service.configured(),
        "public_key": (
            service.settings.push_vapid_public_key if service.configured() else ""
        ),
        "enabled": bool(pref and pref.enabled),
        "categories": pref.categories if pref else service.CATEGORIES,
    }


@router.patch(
    "/api/v1/lodges/{lodge_id}/push/preferences", dependencies=[Depends(require_csrf)]
)
def change_preferences(
    lodge_id: str,
    body: Preferences,
    request: Request,
    user=Depends(require_permission("notifications.view", write=True)),
    db=Depends(get_db),
):
    ensure_feature(db, lodge_id, "notifications")
    pref = db.get(PushPreference, (uuid.UUID(lodge_id), user.id))
    if not pref:
        pref = PushPreference(lodge_id=uuid.UUID(lodge_id), user_id=user.id)
        db.add(pref)
    pref.enabled = body.enabled
    pref.categories = body.categories.model_dump()
    audit(db, request, user, lodge_id, "browser_push.preferences_updated")
    db.commit()
    return {"enabled": pref.enabled, "categories": pref.categories}


@router.post(
    "/api/v1/lodges/{lodge_id}/push/subscriptions", dependencies=[Depends(require_csrf)]
)
def subscribe(
    lodge_id: str,
    body: Device,
    request: Request,
    user=Depends(require_permission("notifications.view", write=True)),
    db=Depends(get_db),
):
    ensure_feature(db, lodge_id, "notifications")
    if not service.configured():
        raise HTTPException(
            503, "Browser notifications are not configured for this installation"
        )
    data = service.validate_subscription(body.model_dump())
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash
            == token_hash(request.cookies.get("lodge_session", "")),
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(timezone.utc),
        )
    )
    if not session:
        raise HTTPException(401, "Sign in again before enabling browser notifications")
    digest = hashlib.sha256(data["endpoint"].encode()).hexdigest()
    row = db.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint_hash == digest,
            PushSubscription.user_id == user.id,
            PushSubscription.lodge_id == lodge_id,
        )
    )
    if not row:
        row = PushSubscription(
            lodge_id=uuid.UUID(lodge_id),
            user_id=user.id,
            session_id=session.id,
            endpoint_hash=digest,
            encrypted_subscription=service.encrypt_subscription(data),
        )
        db.add(row)
    else:
        row.session_id = session.id
        row.encrypted_subscription = service.encrypt_subscription(data)
    with db.no_autoflush:
        pref = db.get(PushPreference, (uuid.UUID(lodge_id), user.id))
    if not pref:
        pref = PushPreference(
            lodge_id=uuid.UUID(lodge_id),
            user_id=user.id,
            categories=dict(service.CATEGORIES),
        )
        db.add(pref)
    pref.enabled = True
    audit(db, request, user, lodge_id, "browser_push.enabled")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Remove the previous browser notification connection before enabling it again",
        )
    return {"id": str(row.id), "enabled": True}


@router.delete("/api/v1/auth/push/subscriptions", dependencies=[Depends(require_csrf)])
def unsubscribe(
    body: RemoveDevice, request: Request, user=Depends(current_user), db=Depends(get_db)
):
    # Own-device privacy opt-out remains available without operational write access.
    set_rls_context(db, str(body.lodge_id), False, str(user.id))
    removed = db.scalar(
        delete(PushSubscription)
        .where(
            PushSubscription.id == body.id,
            PushSubscription.lodge_id == body.lodge_id,
            PushSubscription.user_id == user.id,
        )
        .returning(PushSubscription.id)
    )
    if removed:
        audit(db, request, user, str(body.lodge_id), "browser_push.disabled")
    db.commit()
    return {"ok": True}
