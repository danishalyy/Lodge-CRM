"""Encrypted browser bindings and durable push. Payloads never carry guest data."""

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import UUID
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException
from sqlalchemy import select, and_, or_, delete
from pywebpush import webpush
from .config import settings
from .db import set_rls_context
from .models import (
    PushPreference,
    PushSubscription,
    PushDelivery,
    Notification,
    NotificationRecipient,
    AuthSession,
    User,
)

CATEGORIES = {"task_assigned": True, "request": True, "overdue": True, "arrival": True}
EVENTS = {
    "task.assigned": ("task_assigned", "task"),
    "guest_request.assigned": ("request", "request"),
    "task.overdue": ("overdue", "task"),
    "room.arrival_not_ready": ("arrival", "stay"),
}


def decode_key(value):
    if not isinstance(value, str) or len(value) > 200:
        raise ValueError("Invalid push key")
    return base64.b64decode(
        value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
    )


def configured():
    try:
        private = decode_key(settings.push_vapid_private_key)
        if len(private) != 32:
            return False
        public = (
            ec.derive_private_key(int.from_bytes(private, "big"), ec.SECP256R1())
            .public_key()
            .public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
        )
        Fernet(settings.push_encryption_key.encode())
        subject = urlsplit(settings.push_vapid_subject)
        return public == decode_key(settings.push_vapid_public_key) and (
            subject.scheme == "mailto"
            and "@" in subject.path
            or subject.scheme == "https"
            and bool(subject.hostname)
        )
    except Exception:
        return False


def validate_subscription(data):
    try:
        endpoint = data["endpoint"]
        parts = urlsplit(endpoint)
        host = parts.hostname or ""
        if (
            len(endpoint) > 2048
            or parts.scheme != "https"
            or parts.port not in (None, 443)
            or parts.username
            or parts.password
            or parts.fragment
        ):
            raise ValueError()
        if host not in {
            "fcm.googleapis.com",
            "updates.push.services.mozilla.com",
            "web.push.apple.com",
        } and not host.endswith(".notify.windows.com"):
            raise ValueError()
        keys = data["keys"]
        public = decode_key(keys["p256dh"])
        auth = decode_key(keys["auth"])
        if len(auth) != 16 or len(public) != 65:
            raise ValueError()
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public)
        return {
            "endpoint": endpoint,
            "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]},
        }
    except Exception:
        raise HTTPException(
            422,
            "This browser push subscription is invalid or its delivery service is unsupported",
        )


def encrypt_subscription(data):
    return (
        Fernet(settings.push_encryption_key.encode())
        .encrypt(json.dumps(data).encode())
        .decode()
    )


def queue_push(db, notification, user):
    if (
        user.is_super_admin
        or notification.notification_type not in EVENTS
        or not configured()
    ):
        return
    # Intent is atomic with the notification. Only the worker can see/decrypt
    # other users' devices; operational callers cannot read their bindings.
    db.add(
        PushDelivery(
            lodge_id=notification.lodge_id,
            user_id=user.id,
            notification_id=notification.id,
        )
    )


def authorized(db, row, sub, notification, now):
    from .security import (
        access_context,
        has_permission,
        ensure_subscription_read_allowed,
        ensure_feature,
    )
    from .live_events import visible, RULES

    user = db.get(User, row.user_id)
    session = db.get(AuthSession, sub.session_id)
    if (
        not user
        or not user.is_active
        or user.is_super_admin
        or not session
        or session.user_id != user.id
        or session.revoked_at
        or session.expires_at <= now
    ):
        return False
    if (
        not notification
        or notification.created_at < now - timedelta(days=1)
        or notification.notification_type not in EVENTS
    ):
        return False
    recipient = db.scalar(
        select(NotificationRecipient).where(
            NotificationRecipient.notification_id == notification.id,
            NotificationRecipient.user_id == user.id,
            NotificationRecipient.lodge_id == row.lodge_id,
        )
    )
    if not recipient or recipient.read_at or recipient.archived_at:
        return False
    pref = db.get(PushPreference, (row.lodge_id, row.user_id))
    category, entity = EVENTS[notification.notification_type]
    if not pref or not pref.enabled or not pref.categories.get(category, False):
        return False
    try:
        ctx = access_context(db, user, str(row.lodge_id))
        if ctx.staff and ctx.staff.employment_status != "active":
            return False
        ensure_subscription_read_allowed(db, str(row.lodge_id))
        ensure_feature(db, str(row.lodge_id), "notifications")
        _, permission, feature = RULES[entity]
        ensure_feature(db, str(row.lodge_id), feature)
        if not has_permission(
            db, ctx.membership, "notifications.view"
        ) or not has_permission(db, ctx.membership, permission):
            return False
        return visible(
            db,
            ctx,
            {permission},
            {feature},
            SimpleNamespace(
                entity=entity,
                entity_id=UUID(notification.resource_id),
                lodge_id=row.lodge_id,
            ),
        )
    except (HTTPException, ValueError, TypeError):
        return False


class NoRedirectSession(requests.Session):
    def request(self, *args, **kwargs):
        kwargs["allow_redirects"] = False
        return super().request(*args, **kwargs)


def deliver(sub):
    data = json.loads(
        Fernet(settings.push_encryption_key.encode()).decrypt(
            sub.encrypted_subscription.encode()
        )
    )
    validate_subscription(data)  # Defense in depth against corrupted/imported rows.
    with NoRedirectSession() as client:
        return webpush(
            subscription_info=data,
            data=json.dumps({"type": "notification", "binding": str(sub.id)}),
            vapid_private_key=settings.push_vapid_private_key,
            vapid_claims={"sub": settings.push_vapid_subject},
            ttl=300,
            timeout=10,
            requests_session=client,
        )


def process_push(session_factory, limit=50):
    # Remove expired capabilities even when delivery is temporarily unconfigured.
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        set_rls_context(db, None, True)
        expired = select(AuthSession.id).where(
            or_(AuthSession.revoked_at.is_not(None), AuthSession.expires_at <= now)
        )
        stale = (
            select(PushSubscription.id)
            .where(PushSubscription.session_id.in_(expired))
            .limit(1000)
        )
        db.execute(delete(PushSubscription).where(PushSubscription.id.in_(stale)))
        old = (
            select(PushDelivery.id)
            .where(
                PushDelivery.status.in_(["sent", "cancelled", "dead", "expanded"]),
                PushDelivery.next_attempt_at < now - timedelta(days=8),
            )
            .limit(1000)
        )
        db.execute(delete(PushDelivery).where(PushDelivery.id.in_(old)))
        db.commit()
    if not configured():
        return {"processed": 0}
    processed = 0
    for _ in range(limit):
        now = datetime.now(timezone.utc)
        with session_factory() as db:
            set_rls_context(db, None, True)
            row = db.scalar(
                select(PushDelivery)
                .where(
                    or_(
                        and_(
                            PushDelivery.status.in_(["pending", "failed"]),
                            PushDelivery.next_attempt_at <= now,
                        ),
                        and_(
                            PushDelivery.status == "sending",
                            PushDelivery.lease_expires_at <= now,
                        ),
                    )
                )
                .order_by(PushDelivery.next_attempt_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not row:
                break
            if row.subscription_id is None:
                subs = db.scalars(
                    select(PushSubscription).where(
                        PushSubscription.user_id == row.user_id,
                        PushSubscription.lodge_id == row.lodge_id,
                    )
                ).all()
                notice = db.get(Notification, row.notification_id)
                for sub in subs:
                    if authorized(db, row, sub, notice, now) and not db.scalar(
                        select(PushDelivery.id).where(
                            PushDelivery.subscription_id == sub.id,
                            PushDelivery.notification_id == row.notification_id,
                        )
                    ):
                        db.add(
                            PushDelivery(
                                lodge_id=row.lodge_id,
                                user_id=row.user_id,
                                subscription_id=sub.id,
                                notification_id=row.notification_id,
                            )
                        )
                row.status = "expanded"
                db.commit()
                continue
            row.status = "sending"
            row.attempts += 1
            row.lease_expires_at = now + timedelta(seconds=60)
            key, attempt = row.id, row.attempts
            db.commit()
        with session_factory() as db:
            set_rls_context(db, None, True)
            row = db.scalar(
                select(PushDelivery).where(PushDelivery.id == key).with_for_update()
            )
            if not row or row.status != "sending" or row.attempts != attempt:
                continue
            sub = db.get(PushSubscription, row.subscription_id)
            notice = db.get(Notification, row.notification_id)
            if not sub or not authorized(
                db, row, sub, notice, datetime.now(timezone.utc)
            ):
                row.status = "cancelled"
                row.lease_expires_at = None
                db.commit()
                continue
            try:
                response = deliver(sub)
                code = response.status_code
            except Exception as exc:
                response = getattr(exc, "response", None)
                code = response.status_code if response is not None else 0
            if code in (404, 410):
                db.delete(sub)  # Also removes its stale outbox jobs.
            elif 200 <= code < 300:
                row.status = "sent"
                row.last_error_code = ""
                row.lease_expires_at = None
            else:
                row.status = (
                    "dead" if row.attempts >= 8 or code in (400, 401, 403) else "failed"
                )
                row.last_error_code = (
                    f"push_http_{code}" if code else "push_unavailable"
                )
                row.next_attempt_at = now + timedelta(
                    seconds=min(3600, 30 * 2 ** (row.attempts - 1))
                )
                row.lease_expires_at = None
            db.commit()
            processed += 1
    return {"processed": processed}
