from datetime import datetime, timezone
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import settings
from .models import (
    Membership, Notification, NotificationDelivery, NotificationPreference,
    NotificationRecipient, Permission, RolePermission, StaffProfile, User, Role,
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
        user=db.get(User,user_id)
        if not user or not user.is_active:continue
        if not user.is_super_admin:
            member=db.scalar(select(Membership).where(Membership.lodge_id==lodge_id,Membership.user_id==user.id,Membership.is_active.is_(True)))
            staff=db.scalar(select(StaffProfile).where(StaffProfile.user_id==user.id,StaffProfile.lodge_id==lodge_id))
            if not member or (staff and staff.employment_status!="active"):continue
        db.add(NotificationRecipient(lodge_id=lodge_id,notification_id=notification.id,user_id=user_id))
        pref=db.scalar(select(NotificationPreference).where(NotificationPreference.lodge_id==lodge_id,NotificationPreference.user_id==user_id))
        enabled=pref.email_enabled if pref else user.email_notifications_enabled
        minimum=pref.email_min_severity if pref else user.email_min_severity
        if not enabled or not user.email_notifications_enabled or not user.email_verified_at or SEVERITY_RANK[severity]<SEVERITY_RANK.get(minimum,2):continue
        db.add(NotificationDelivery(lodge_id=lodge_id,notification_id=notification.id,user_id=user_id,channel="email",destination=user.email,
                                   idempotency_key=f"email:{notification.id}:{user_id}",status="pending",next_attempt_at=datetime.now(timezone.utc)))
    return notification


def management_recipient_ids(db, lodge_id, permission_key, department_id=None):
    """Operational notices go to responsible managers, not everyone with inbox access."""
    from .security import has_permission
    rows=db.execute(select(Membership,Role,User).join(Role,Role.id==Membership.role_id).join(User,User.id==Membership.user_id)
                    .where(Membership.lodge_id==lodge_id,Membership.is_active.is_(True),User.is_active.is_(True))).all()
    out=[]
    for member,role,user in rows:
        if role.key not in {"lodge_admin","group_admin","department_manager"}:continue
        if role.key=="department_manager" and (not department_id or member.department_id!=department_id):continue
        if not has_permission(db,member,permission_key):continue
        staff=db.scalar(select(StaffProfile).where(StaffProfile.user_id==user.id,StaffProfile.lodge_id==lodge_id))
        if staff and staff.employment_status!="active":continue
        out.append(user.id)
    return out
