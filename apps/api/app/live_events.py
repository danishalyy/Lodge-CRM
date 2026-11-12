"""Private, resumable SSE invalidations. No business data enters the stream."""
import asyncio
import base64
import hashlib
import json
import time
import uuid
import anyio
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select, func, or_
from sqlalchemy.orm import sessionmaker
from starlette.responses import StreamingResponse
from .db import get_db, set_rls_context
from .models import (LiveEvent, Task, GuestRequest, Unit, Stay, HousekeepingJob, MaintenanceTicket, NotificationRecipient, Permission, RolePermission, CustomRolePermission, CustomRole, PlanEntitlement, LodgeEntitlementOverride, Subscription)
from .security import (_current_user, require_lodge_access, access_context, ensure_subscription_read_allowed, subscription_state)
from .feature_catalog import BUILT

router = APIRouter()
POLL_SECONDS = 1.0
HEARTBEAT_SECONDS = 15.0
MAX_STREAM_SECONDS = 300.0
RULES = {'task':(Task,'tasks.view','tasks'), 'request':(GuestRequest,'requests.view','guest_requests'), 'room':(Unit,'units.view','units'), 'stay':(Stay,'stays.view','stays'), 'housekeeping':(HousekeepingJob,'housekeeping.view','housekeeping'), 'maintenance':(MaintenanceTicket,'maintenance.view','maintenance')}
OWN_TASK_ROLES = {'housekeeping','ranger','maintenance','driver','fb','general_staff'}

def authorize(db, token, user_id, lodge_id):
    user = _current_user(token, db, str(user_id), str(lodge_id))
    if user.is_super_admin: raise HTTPException(403,'Platform accounts cannot access lodge operations')
    ctx = access_context(db,user,str(lodge_id))
    set_rls_context(db,str(lodge_id),False,str(user.id))
    ensure_subscription_read_allowed(db,str(lodge_id))
    member=ctx.membership
    if member.custom_role_id:
        permissions=set(db.scalars(select(Permission.key).join(CustomRolePermission,CustomRolePermission.permission_id==Permission.id).join(CustomRole,CustomRole.id==CustomRolePermission.custom_role_id).where(CustomRole.id==member.custom_role_id,CustomRole.is_active.is_(True),CustomRole.lodge_id==lodge_id)).all())
    else:
        permissions=set(db.scalars(select(Permission.key).join(RolePermission,RolePermission.permission_id==Permission.id).where(RolePermission.role_id==member.role_id)).all())
    sub=db.get(Subscription,lodge_id)
    features=set(db.scalars(select(PlanEntitlement.feature_key).where(PlanEntitlement.plan_key==sub.package,PlanEntitlement.enabled.is_(True))).all()) if sub else set()
    for row in db.scalars(select(LodgeEntitlementOverride).where(LodgeEntitlementOverride.lodge_id==lodge_id)).all():
        if row.enabled: features.add(row.feature_key)
        else: features.discard(row.feature_key)
    features &= set(BUILT)
    fingerprint=hashlib.sha256(json.dumps([str(user.id),str(lodge_id),ctx.role_key,str(ctx.department_id),str(ctx.staff.id) if ctx.staff else None,str(ctx.staff.department_id) if ctx.staff else None,str(member.custom_role_id),sorted(permissions),sorted(features),subscription_state(db,lodge_id)[1],str(user.mfa_enabled_at)],sort_keys=True).encode()).hexdigest()
    return ctx,permissions,features,fingerprint

def visible(db,ctx,permissions,features,row):
    if row.entity=='subscription':return True
    if row.entity=='notification':
        return db.scalar(select(NotificationRecipient.id).where(NotificationRecipient.lodge_id==row.lodge_id,NotificationRecipient.notification_id==row.entity_id,NotificationRecipient.user_id==ctx.user.id).limit(1)) is not None
    rule=RULES.get(row.entity)
    if not rule:return False
    model,permission,feature=rule
    if permission not in permissions or feature not in features:return False
    q=select(model.id).where(model.id==row.entity_id,model.lodge_id==row.lodge_id)
    if row.entity=='task':
        if ctx.role_key=='department_manager':
            if not ctx.department_id:return False
            q=q.where(Task.department_id==ctx.department_id)
        elif ctx.role_key in OWN_TASK_ROLES:
            if not ctx.staff:return False
            q=q.where(Task.assigned_staff_id==ctx.staff.id)
    elif row.entity=='request':
        if ctx.role_key=='department_manager':
            if not ctx.department_id:return False
            q=q.where(GuestRequest.department_id==ctx.department_id)
        elif ctx.role_key in {'housekeeping','fb','general_staff'}:
            if not ctx.staff:return False
            q=q.where(GuestRequest.assigned_staff_id==ctx.staff.id) if ctx.role_key=='general_staff' else q.where(or_(GuestRequest.assigned_staff_id==ctx.staff.id,GuestRequest.department_id==ctx.staff.department_id))
    elif row.entity=='maintenance':
        if ctx.role_key=='department_manager':
            if not ctx.department_id:return False
            q=q.where(MaintenanceTicket.department_id==ctx.department_id)
        elif ctx.role_key in {'housekeeping','ranger','driver','general_staff'}:
            if not ctx.staff:return False  # stricter than a NULL-assignee comparison
            q=q.where(or_(MaintenanceTicket.created_by_user_id==ctx.user.id,MaintenanceTicket.assigned_staff_id==ctx.staff.id))
    elif row.entity=='housekeeping':
        if ctx.role_key=='housekeeping':
            if not ctx.staff:return False
            q=q.where(HousekeepingJob.assigned_staff_id==ctx.staff.id)
        elif ctx.role_key=='department_manager':
            if not ctx.department_id:return False
            from .models import StaffProfile
            q=q.join(StaffProfile,StaffProfile.id==HousekeepingJob.assigned_staff_id).where(StaffProfile.department_id==ctx.department_id)
    return db.scalar(q.limit(1)) is not None

def cipher(token):return Fernet(base64.urlsafe_b64encode(hashlib.sha256(token.encode()).digest()))
def encode_cursor(token,lodge_id,user_id,fingerprint,position):
    return cipher(token).encrypt(f'{lodge_id}:{user_id}:{fingerprint}:{position:020d}'.encode()).decode()
def decode_cursor(value,token,lodge_id,user_id,fingerprint):
    try:
        if len(value)>2048:raise ValueError()
        lodge,user,prior,position=cipher(token).decrypt(value.encode(),ttl=7*86400).decode().split(':')
        if lodge!=str(lodge_id) or user!=str(user_id):raise ValueError()
        return int(position) if prior==fingerprint else None
    except (InvalidToken,ValueError,TypeError,UnicodeError):raise HTTPException(400,'Live update cursor is invalid; reconnect without it')

def head(db,lodge_id):return db.scalar(select(func.max(LiveEvent.id)).where(LiveEvent.lodge_id==lodge_id)) or 0

def read_page(factory,token,user_id,lodge_id,position,fingerprint):
    with factory() as db:
        ctx,permissions,features,current=authorize(db,token,user_id,lodge_id)
        if current!=fingerprint:return position,[],True
        rows=db.scalars(select(LiveEvent).where(LiveEvent.lodge_id==lodge_id,LiveEvent.id>position).order_by(LiveEvent.id).limit(200)).all()
        output=[{'type':r.kind,'id':str(r.entity_id),'version':str(r.version)} for r in rows if visible(db,ctx,permissions,features,r)]
        return (rows[-1].id if rows else position),output,False

def frame(event,data,cursor=None):
    return (f'id: {cursor}\n' if cursor else '')+f'event: {event}\ndata: {json.dumps(data,separators=(",",":"))}\n\n'

@router.get('/api/v1/lodges/{lodge_id}/events')
def events(lodge_id:uuid.UUID,request:Request,last_event_id:str|None=Header(None),user=Depends(require_lodge_access),db=Depends(get_db)):
    token=request.cookies.get('lodge_session','')
    _,_,_,fingerprint=authorize(db,token,user.id,lodge_id)
    high=head(db,lodge_id)
    position=decode_cursor(last_event_id,token,lodge_id,user.id,fingerprint) if last_event_id else None
    if position is not None and (position<0 or position>high):raise HTTPException(400,'Live update cursor is invalid; reconnect without it')
    if position is None:position=high
    factory=sessionmaker(bind=db.get_bind(),expire_on_commit=False)
    user_id=user.id
    db.rollback() # do not pin a request transaction/connection for a long stream
    async def stream():
        nonlocal position
        started=last_heartbeat=time.monotonic()
        yield 'retry: 3000\n'+frame('ready',{'type':'access.snapshot','id':str(lodge_id),'version':fingerprint},encode_cursor(token,lodge_id,user_id,fingerprint,position))
        while time.monotonic()-started<MAX_STREAM_SECONDS:
            if await request.is_disconnected():return
            try:
                position,changes,changed=await anyio.to_thread.run_sync(lambda:read_page(factory,token,user_id,lodge_id,position,fingerprint))
            except HTTPException:
                yield frame('access',{'type':'access.changed','id':str(lodge_id),'version':str(uuid.uuid4())});return
            if changed:
                yield frame('access',{'type':'access.changed','id':str(lodge_id),'version':str(uuid.uuid4())});return
            for change in changes:
                # All changes in a page share its safe checkpoint: the client
                # must consume the full page before reconnecting from that ID.
                yield frame('change',change)
            if changes:
                yield frame('checkpoint',{},encode_cursor(token,lodge_id,user_id,fingerprint,position))
            if time.monotonic()-last_heartbeat>=HEARTBEAT_SECONDS:
                yield ': keepalive\n'+frame('heartbeat',{},encode_cursor(token,lodge_id,user_id,fingerprint,position));last_heartbeat=time.monotonic()
            await asyncio.sleep(POLL_SECONDS)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-store, no-transform','X-Accel-Buffering':'no','Vary':'Cookie, X-Expected-User-Id, X-Lodge-Context'})
