"""Account invitation, personal notification inbox, and platform mail delivery routes."""
from datetime import datetime, timedelta, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select, func, or_
from .config import settings
from .db import get_db, set_rls_context
from .models import AccountEmail, Invitation, User, Lodge, Membership, Role, StaffProfile, Notification, NotificationRecipient, NotificationDelivery, NotificationPreference
from .schemas import PlatformInvite, InvitationPreviewIn, NotificationPreferenceUpdate
from .security import current_user, require_super_admin, require_permission, require_csrf, hash_password, new_token, token_hash
from .email_service import issue_invitation, account_email_status, email_configured, queue_account_email

router = APIRouter()


def _audit(db, request, actor, action, target, lodge_id=None):
    from .models import AuditLog
    db.add(AuditLog(lodge_id=lodge_id, actor_user_id=actor.id, action=action, resource_type="user", resource_id=str(target), request_id=request.headers.get("x-request-id", ""), ip_address=request.client.host if request.client else ""))


@router.post('/api/v1/auth/invitations/preview')
def preview_invitation(body: InvitationPreviewIn, db=Depends(get_db)):
    set_rls_context(db, None, True)
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == token_hash(body.token), Invitation.used_at.is_(None), Invitation.expires_at > datetime.now(timezone.utc)))
    user = db.get(User, inv.user_id) if inv else None
    if not user or user.is_active:
        raise HTTPException(400, 'This invitation is invalid, expired, or already used. Ask your administrator to resend it.')
    lodge = db.get(Lodge, inv.lodge_id) if inv.lodge_id else None
    if inv.lodge_id and not db.scalar(select(Membership).where(Membership.lodge_id == inv.lodge_id, Membership.user_id == user.id, Membership.is_active.is_(True))):
        raise HTTPException(400, 'This invitation is no longer available.')
    if inv.lodge_id:
        staff=db.scalar(select(StaffProfile).where(StaffProfile.lodge_id==inv.lodge_id,StaffProfile.user_id==user.id))
        if staff and staff.employment_status!='active':raise HTTPException(400,'This invitation is no longer available.')
    address, domain = user.email.split('@', 1)
    return {'name': user.full_name, 'email_hint': address[:1] + '***@' + domain,
            'workspace': (lodge.brand_name or lodge.name) if lodge else 'SafariOS platform', 'expires_at': inv.expires_at.isoformat()}


@router.post('/api/v1/platform/users/invite', dependencies=[Depends(require_csrf)])
def invite_platform_user(body: PlatformInvite, request: Request, actor: User = Depends(require_super_admin), db=Depends(get_db)):
    set_rls_context(db, None, True, str(actor.id))
    if db.scalar(select(User).where(func.lower(User.email) == str(body.email).lower())):
        raise HTTPException(409, 'This email already has an account. Resend the invitation if it is pending.')
    target = User(email=str(body.email).lower(), full_name=body.full_name.strip(), password_hash=hash_password(new_token() + new_token()), is_active=False, is_super_admin=True)
    db.add(target)
    db.flush()
    result = issue_invitation(db, target, creator_id=actor.id)
    _audit(db, request, actor, 'platform.user.invited', target.id)
    db.commit()
    return {'user_id': str(target.id), **result}


@router.post('/api/v1/platform/users/{user_id}/invitation', dependencies=[Depends(require_csrf)])
def resend_platform_invitation(user_id: uuid.UUID, request: Request, actor: User = Depends(require_super_admin), db=Depends(get_db)):
    set_rls_context(db, None, True, str(actor.id))
    target = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not target:
        raise HTTPException(404, 'User not found')
    member = db.scalar(select(Membership).where(Membership.user_id == target.id, Membership.is_active.is_(True)))
    if not target.is_super_admin and not member:
        raise HTTPException(409, 'This account has no active lodge membership.')
    lodge = db.get(Lodge, member.lodge_id) if member else None
    result = issue_invitation(db, target, lodge=lodge, creator_id=actor.id)
    _audit(db, request, actor, 'account.invitation.resent', target.id, lodge.id if lodge else None)
    db.commit()
    return result


@router.post('/api/v1/lodges/{lodge_id}/staff/{record_id}/invitation/resend', dependencies=[Depends(require_csrf)])
def resend_staff_invitation(lodge_id: str, record_id: uuid.UUID, request: Request, actor: User = Depends(require_permission('staff.manage', write=True)), db=Depends(get_db)):
    staff = db.scalar(select(StaffProfile).where(StaffProfile.id == record_id, StaffProfile.lodge_id == lodge_id))
    if not staff or not staff.user_id:
        raise HTTPException(404, 'Staff login not found')
    from .security import access_context
    ctx=access_context(db,actor,lodge_id)
    if ctx.role_key=='department_manager' and (not ctx.department_id or staff.department_id!=ctx.department_id):raise HTTPException(403,'Only staff in your department can be invited.')
    if staff.employment_status != 'active':
        raise HTTPException(409, 'Only active staff can be invited.')
    target = db.scalar(select(User).where(User.id == staff.user_id).with_for_update())
    member = db.scalar(select(Membership).where(Membership.user_id == target.id, Membership.lodge_id == lodge_id, Membership.is_active.is_(True))) if target else None
    if not target or target.is_super_admin or not member:
        raise HTTPException(409, 'This staff account cannot be invited.')
    result = issue_invitation(db, target, lodge=db.get(Lodge, lodge_id), creator_id=actor.id)
    _audit(db, request, actor, 'account.invitation.resent', target.id, lodge_id)
    db.commit()
    return result


def _mail_status(row):
    return {'id': str(row.id), 'user_id': str(row.user_id), 'destination': row.destination, 'kind': row.kind,
            'status': row.status, 'attempts': row.attempts, 'last_error': row.last_error,
            'created_at': row.created_at.isoformat(), 'sent_at': row.sent_at.isoformat() if row.sent_at else None,
            'next_attempt_at': row.next_attempt_at.isoformat() if row.status in {'pending', 'failed'} else None}


@router.get('/api/v1/platform/email')
def platform_email(actor: User = Depends(require_super_admin), db=Depends(get_db)):
    set_rls_context(db, None, True, str(actor.id))
    rows = db.scalars(select(AccountEmail).order_by(AccountEmail.created_at.desc()).limit(100)).all()
    return {'configured': email_configured(), 'provider': 'Gmail / Google Workspace' if settings.smtp_host.lower() == 'smtp.gmail.com' else 'SMTP',
            'sender': settings.smtp_from_email or None, 'encrypted_transport': settings.smtp_use_tls or settings.smtp_use_ssl,
            'outbox_encryption_configured': bool(settings.email_encryption_key or settings.mfa_encryption_key),
            'account_deliveries': [_mail_status(row) for row in rows]}


@router.post('/api/v1/platform/email/test', dependencies=[Depends(require_csrf)])
def test_platform_email(request: Request, actor: User = Depends(require_super_admin), db=Depends(get_db)):
    set_rls_context(db, None, True, str(actor.id))
    if db.scalar(select(AccountEmail.id).where(AccountEmail.created_by_user_id == actor.id, AccountEmail.kind == 'test', AccountEmail.created_at > datetime.now(timezone.utc) - timedelta(minutes=1))):
        raise HTTPException(429, 'Wait one minute before requesting another test email.')
    row = queue_account_email(db, user=actor, kind='test', title='Your SafariOS email connection test',
                               body='This is a test of your SafariOS sender. Account invitations and operational emails use this same connection.', created_by_user_id=actor.id)
    _audit(db, request, actor, 'email.test.queued', actor.id)
    db.commit()
    return {'id': str(row.id), 'status': row.status, 'destination': actor.email}


def _inbox_context(db, user):
    if user.is_super_admin:
        set_rls_context(db, None, True, str(user.id))
    else:
        member = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.is_active.is_(True)))
        set_rls_context(db, str(member.lodge_id) if member else None, False, str(user.id))
        if member:
            from .security import ensure_subscription_read_allowed
            ensure_subscription_read_allowed(db,str(member.lodge_id))
            staff=db.scalar(select(StaffProfile).where(StaffProfile.user_id==user.id,StaffProfile.lodge_id==member.lodge_id))
            if staff and staff.employment_status!='active':raise HTTPException(403,'Account access is unavailable')


def _inbox(db, user):
    _inbox_context(db, user)
    return (select(NotificationRecipient, Notification).join(Notification, Notification.id == NotificationRecipient.notification_id)
            .where(NotificationRecipient.user_id == user.id, NotificationRecipient.archived_at.is_(None),
                   or_(Notification.expires_at.is_(None), Notification.expires_at > datetime.now(timezone.utc))))


@router.get('/api/v1/auth/notifications/summary')
def notification_summary(user: User = Depends(current_user), db=Depends(get_db)):
    from .email_jobs import notification_still_authorized
    rows=db.execute(_inbox(db,user).where(NotificationRecipient.read_at.is_(None))).all()
    return {'unread': sum(1 for _,notice in rows if notification_still_authorized(db,notice,user))}


@router.get('/api/v1/auth/notifications')
def account_notifications(unread_only: bool = False, severity: str | None = None, limit: int = Query(100, ge=1, le=250), user: User = Depends(current_user), db=Depends(get_db)):
    query = _inbox(db, user)
    if unread_only:
        query = query.where(NotificationRecipient.read_at.is_(None))
    if severity:
        if severity not in {'low', 'normal', 'high', 'critical'}:
            raise HTTPException(422, 'Invalid priority')
        query = query.where(Notification.severity == severity)
    rows = db.execute(query.order_by(Notification.created_at.desc()).limit(limit)).all()
    out = []
    for recipient, notification in rows:
        from .email_jobs import notification_still_authorized
        if not notification_still_authorized(db,notification,user):continue
        delivery = db.scalar(select(NotificationDelivery).where(NotificationDelivery.notification_id == notification.id, NotificationDelivery.user_id == user.id))
        out.append({'id': str(notification.id), 'type': notification.notification_type, 'severity': notification.severity,
                    'title': notification.title, 'body': notification.body, 'resource_type': notification.resource_type,
                    'resource_id': notification.resource_id, 'lodge_id': str(notification.lodge_id),
                    'created_at': notification.created_at.isoformat(), 'read_at': recipient.read_at.isoformat() if recipient.read_at else None,
                    'email_status': delivery.status if delivery else None})
    return out


@router.post('/api/v1/auth/notifications/read-all', dependencies=[Depends(require_csrf)])
def read_all_notifications(user: User = Depends(current_user), db=Depends(get_db)):
    rows = db.execute(_inbox(db, user).where(NotificationRecipient.read_at.is_(None))).all()
    for recipient, _ in rows:
        recipient.read_at = datetime.now(timezone.utc)
    db.commit()
    return {'ok': True}


@router.post('/api/v1/auth/notifications/{notification_id}/read', dependencies=[Depends(require_csrf)])
def read_account_notification(notification_id: uuid.UUID, user: User = Depends(current_user), db=Depends(get_db)):
    row = db.execute(_inbox(db, user).where(Notification.id == notification_id)).first()
    if not row:
        raise HTTPException(404, 'Notification not found')
    row[0].read_at = row[0].read_at or datetime.now(timezone.utc)
    db.commit()
    return {'ok': True}


@router.post('/api/v1/auth/notifications/{notification_id}/archive', dependencies=[Depends(require_csrf)])
def archive_account_notification(notification_id: uuid.UUID, user: User = Depends(current_user), db=Depends(get_db)):
    row = db.execute(_inbox(db, user).where(Notification.id == notification_id)).first()
    if not row:
        raise HTTPException(404, 'Notification not found')
    row[0].archived_at = datetime.now(timezone.utc)
    db.commit()
    return {'ok': True}


@router.get('/api/v1/auth/notification-preferences')
def personal_notification_preferences(user: User = Depends(current_user)):
    return {'email_enabled': user.email_notifications_enabled, 'email_min_severity': user.email_min_severity,
            'email_verified': bool(user.email_verified_at), 'email_configured': email_configured()}


@router.patch('/api/v1/auth/notification-preferences', dependencies=[Depends(require_csrf)])
def save_personal_notification_preferences(body: NotificationPreferenceUpdate, user: User = Depends(current_user), db=Depends(get_db)):
    _inbox_context(db, user)
    user.email_notifications_enabled = body.email_enabled
    user.email_min_severity = body.email_min_severity
    for pref in db.scalars(select(NotificationPreference).where(NotificationPreference.user_id == user.id)).all():
        pref.email_enabled = body.email_enabled
        pref.email_min_severity = body.email_min_severity
    db.commit()
    return personal_notification_preferences(user)


@router.post('/api/v1/platform/email/{record_id}/retry', dependencies=[Depends(require_csrf)])
def retry_account_email(record_id: uuid.UUID, request: Request, actor: User = Depends(require_super_admin), db=Depends(get_db)):
    set_rls_context(db, None, True, str(actor.id))
    row = db.scalar(select(AccountEmail).where(AccountEmail.id == record_id).with_for_update())
    if not row:
        raise HTTPException(404, 'Email delivery not found')
    if row.status not in {'failed', 'dead'} or not row.encrypted_payload:
        raise HTTPException(409, 'Only failed email deliveries can be retried.')
    if row.invitation_id:
        inv = db.get(Invitation, row.invitation_id)
        if not inv or inv.used_at or inv.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(409, 'This link has expired or been used. Send a new invitation instead.')
    row.status, row.attempts, row.last_error = 'pending', 0, ''
    row.next_attempt_at = datetime.now(timezone.utc)
    row.lease_expires_at = None
    _audit(db, request, actor, 'email.delivery.retried', row.user_id, row.lodge_id)
    db.commit()
    return {'id': str(row.id), 'status': row.status}


@router.post('/api/v1/lodges/{lodge_id}/notification-deliveries/{record_id}/retry', dependencies=[Depends(require_csrf)])
def retry_notification_delivery(lodge_id: str, record_id: uuid.UUID, request: Request, actor: User = Depends(require_permission('notifications.delivery.view', write=True)), db=Depends(get_db)):
    row = db.scalar(select(NotificationDelivery).where(NotificationDelivery.id == record_id, NotificationDelivery.lodge_id == lodge_id).with_for_update())
    if not row:
        raise HTTPException(404, 'Email delivery not found')
    if row.status not in {'failed', 'dead'}:
        raise HTTPException(409, 'Only failed email deliveries can be retried.')
    row.status, row.attempts, row.last_error = 'pending', 0, ''
    row.next_attempt_at = datetime.now(timezone.utc)
    row.lease_expires_at = None
    _audit(db, request, actor, 'notification.delivery.retried', row.user_id, lodge_id)
    db.commit()
    return {'id': str(row.id), 'status': row.status}
