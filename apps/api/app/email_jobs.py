"""Lease-based mail jobs. Rows survive SMTP/Redis outages and worker restarts."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, or_, select
from .config import settings
from .db import set_rls_context
from .models import AccountEmail, Invitation, PasswordResetToken, User, Notification, NotificationDelivery, NotificationPreference, Membership, StaffProfile, Task, MaintenanceTicket
from .email_service import decrypt_payload, send_email, safe_delivery_error


def _due(model, now):
    return or_(and_(model.status.in_(["pending", "failed"]), model.next_attempt_at <= now),
               and_(model.status == "sending", model.lease_expires_at <= now))


def _retry(row, exc, now):
    row.last_error = safe_delivery_error(exc)
    row.lease_expires_at = None
    row.status = "dead" if row.attempts >= 8 else "failed"
    row.next_attempt_at = now + timedelta(seconds=min(3600, 60 * 2 ** max(0, row.attempts - 1)))


def process_account_emails(session_factory, limit=50):
    processed = 0
    for _ in range(limit):
        now = datetime.now(timezone.utc)
        with session_factory() as db:
            set_rls_context(db, None, True)
            row = db.scalar(select(AccountEmail).where(_due(AccountEmail, now)).order_by(AccountEmail.next_attempt_at)
                            .with_for_update(skip_locked=True).limit(1))
            if not row:
                break
            row.status = "sending"
            row.attempts += 1
            row.lease_expires_at = now + timedelta(minutes=5)
            row_id, attempt = row.id, row.attempts
            db.commit()
        with session_factory() as db:
            set_rls_context(db, None, True)
            row = db.scalar(select(AccountEmail).where(AccountEmail.id == row_id).with_for_update())
            if not row or row.status != "sending" or row.attempts != attempt:
                continue
            user = db.get(User, row.user_id)
            valid = bool(user and user.email.lower() == row.destination.lower())
            if row.invitation_id:
                inv = db.get(Invitation, row.invitation_id)
                valid = valid and not user.is_active and inv and not inv.used_at and inv.expires_at > now
                if valid and inv.lodge_id:
                    member = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.lodge_id == inv.lodge_id, Membership.is_active.is_(True)))
                    staff = db.scalar(select(StaffProfile).where(StaffProfile.user_id == user.id, StaffProfile.lodge_id == inv.lodge_id))
                    valid = bool(member and (not staff or staff.employment_status == "active"))
            elif row.reset_token_id:
                token = db.get(PasswordResetToken, row.reset_token_id)
                valid = valid and user.is_active and token and not token.used_at and token.expires_at > now
            else:
                valid = valid and user.is_active and row.created_at > now - timedelta(days=1)
            if not valid or not row.encrypted_payload:
                row.status = "cancelled"
                row.encrypted_payload = None
                row.lease_expires_at = None
                db.commit()
                continue
            try:
                payload = decrypt_payload(row.encrypted_payload)
                send_email(row.destination, payload["title"], payload["body"], payload["html"], f"<{row.id}@safarios.mail>")
                row.status = "sent"
                row.sent_at = datetime.now(timezone.utc)
                row.encrypted_payload = None
                row.lease_expires_at = None
                row.last_error = ""
            except Exception as exc:
                _retry(row, exc, datetime.now(timezone.utc))
            db.commit()
            processed += 1
    return {"processed": processed}


def notification_still_authorized(db, notification, user):
    from .security import access_context, has_permission
    if notification.notification_type == "subscription.expiry":
        return user.is_super_admin
    try:
        ctx = access_context(db, user, str(notification.lodge_id))
        if not ctx.super_admin:
            from .security import ensure_subscription_read_allowed
            ensure_subscription_read_allowed(db,str(notification.lodge_id))
            if ctx.staff and ctx.staff.employment_status != 'active':return False
            required={'vehicle':'vehicles.view','stay':'guests.view','maintenance_asset':'maintenance.view','staff_credential':'staff.hr.manage'}.get(notification.resource_type)
            if required and not has_permission(db,ctx.membership,required):return False
        if not ctx.super_admin and not has_permission(db, ctx.membership, "notifications.view"):
            return False
        resource = None
        if notification.resource_type == "task":
            resource = db.get(Task, notification.resource_id)
            if not resource or not (ctx.super_admin or has_permission(db, ctx.membership, "tasks.view")):
                return False
            if ctx.role_key in {"general_staff", "housekeeping", "ranger", "maintenance", "driver", "fb"}:
                return bool(ctx.staff and resource.assigned_staff_id == ctx.staff.id)
        elif notification.resource_type == "maintenance":
            resource = db.get(MaintenanceTicket, notification.resource_id)
            if not resource or not (ctx.super_admin or has_permission(db, ctx.membership, "maintenance.view")):
                return False
        if resource and ctx.role_key == "department_manager":
            return bool(ctx.department_id and resource.department_id == ctx.department_id)
        return True
    except Exception:
        return False


def process_notification_emails(session_factory, limit=50):
    processed = 0
    for _ in range(limit):
        now = datetime.now(timezone.utc)
        with session_factory() as db:
            set_rls_context(db, None, True)
            query = or_(_due(NotificationDelivery, now), and_(NotificationDelivery.status == "sending", NotificationDelivery.lease_expires_at.is_(None), NotificationDelivery.updated_at < now - timedelta(minutes=5)))
            row = db.scalar(select(NotificationDelivery).where(query).order_by(NotificationDelivery.next_attempt_at).with_for_update(skip_locked=True).limit(1))
            if not row:
                break
            row.status = "sending"
            row.attempts += 1
            row.lease_expires_at = now + timedelta(minutes=5)
            row_id, attempt = row.id, row.attempts
            db.commit()
        with session_factory() as db:
            set_rls_context(db, None, True)
            row = db.scalar(select(NotificationDelivery).where(NotificationDelivery.id == row_id).with_for_update())
            if not row or row.status != "sending" or row.attempts != attempt:
                continue
            notification, user = db.get(Notification, row.notification_id), db.get(User, row.user_id)
            pref = db.scalar(select(NotificationPreference).where(NotificationPreference.user_id == row.user_id, NotificationPreference.lodge_id == row.lodge_id))
            enabled = pref.email_enabled if pref else user.email_notifications_enabled if user else False
            threshold = pref.email_min_severity if pref else user.email_min_severity if user else "high"
            from .notification_service import SEVERITY_RANK
            valid = bool(notification and user and user.is_active and user.email_verified_at and user.email == row.destination
                         and enabled and user.email_notifications_enabled
                         and SEVERITY_RANK[notification.severity] >= SEVERITY_RANK[threshold]
                         and (not notification.expires_at or notification.expires_at > now)
                         and notification_still_authorized(db, notification, user))
            if not valid:
                row.status = "cancelled"
                row.lease_expires_at = None
                db.commit()
                continue
            try:
                send_email(row.destination, notification.title, notification.body or notification.title, message_id=f"<{row.id}@safarios.mail>")
                row.status = "sent"
                row.sent_at = datetime.now(timezone.utc)
                row.last_error = ""
                row.lease_expires_at = None
            except Exception as exc:
                _retry(row, exc, datetime.now(timezone.utc))
            db.commit()
            processed += 1
    return {"processed": processed}
