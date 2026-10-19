from datetime import datetime, timezone
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import settings
from .models import (
    Membership, Notification, NotificationDelivery, NotificationPreference,
    NotificationRecipient, Permission, RolePermission, StaffProfile, User,
)

SEVERITY_RANK={"low":0,"normal":1,"high":2,"critical":3}

def user_ids_with_permission(db:Session,lodge_id,permission_key:str):
    permission_id=db.scalar(select(Permission.id).where(Permission.key==permission_key))
    if not permission_id:return []
    return list(db.scalars(
        select(Membership.user_id).join(RolePermission,RolePermission.role_id==Membership.role_id)
        .where(Membership.lodge_id==lodge_id,Membership.is_active.is_(True),RolePermission.permission_id==permission_id)
    ).all())

def staff_user_id(db:Session,lodge_id,staff_id):
    if not staff_id:return None
    return db.scalar(select(StaffProfile.user_id).where(StaffProfile.id==staff_id,StaffProfile.lodge_id==lodge_id))

def create_notification(db:Session,*,lodge_id,notification_type:str,severity:str,title:str,body:str="",resource_type:str="",resource_id:str="",dedupe_key:str|None=None,recipient_user_ids=None,created_by_event_id=None):
    if severity not in SEVERITY_RANK: raise ValueError("Invalid notification severity")
    if dedupe_key:
        existing=db.scalar(select(Notification).where(Notification.lodge_id==lodge_id,Notification.dedupe_key==dedupe_key))
        if existing:return existing
    notification=Notification(lodge_id=lodge_id,notification_type=notification_type,severity=severity,title=title,body=body,resource_type=resource_type,resource_id=str(resource_id or ""),dedupe_key=dedupe_key,created_by_event_id=created_by_event_id)
    try:
        with db.begin_nested():
            db.add(notification)
            db.flush()
    except IntegrityError:
        if dedupe_key:
            return db.scalar(select(Notification).where(Notification.lodge_id==lodge_id,Notification.dedupe_key==dedupe_key))
        raise
    user_ids=list(dict.fromkeys([x for x in (recipient_user_ids or []) if x]))
    for user_id in user_ids:
        db.add(NotificationRecipient(lodge_id=lodge_id,notification_id=notification.id,user_id=user_id))
        pref=db.scalar(select(NotificationPreference).where(NotificationPreference.lodge_id==lodge_id,NotificationPreference.user_id==user_id))
        if not pref or not pref.email_enabled or SEVERITY_RANK[severity] < SEVERITY_RANK.get(pref.email_min_severity,2):
            continue
        user=db.get(User,user_id)
        if not user or not user.email: continue
        db.add(NotificationDelivery(
            lodge_id=lodge_id,notification_id=notification.id,user_id=user_id,channel="email",destination=user.email,
            idempotency_key=f"email:{notification.id}:{user_id}",status="pending",next_attempt_at=datetime.now(timezone.utc)
        ))
    return notification
