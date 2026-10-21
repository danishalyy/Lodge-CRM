"""Group owners get explicit lodge memberships, never platform-wide RLS bypass."""
from datetime import datetime,timezone
import uuid
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select,func
from .db import get_db,set_rls_context
from .models import Invitation,LodgeGroup,Lodge,User,Role,Membership,AuditLog,Subscription,Task,Guest,MaintenanceTicket
from .schemas import GroupCreate,GroupUpdate,LodgeAdminInvite
from .security import current_user,require_super_admin,require_permission,require_csrf,membership_for,hash_password,new_token,ensure_subscription_read_allowed,entitlement_enabled,has_permission
from .email_service import issue_invitation,account_email_status
router=APIRouter()

def audit(db,actor,action,record,lodge_id=None,resource_type="lodge_group"):
    db.add(AuditLog(actor_user_id=actor.id,lodge_id=lodge_id,action=action,resource_type=resource_type,resource_id=str(record)))

def sync_lodges(db,group,ids):
    selected=set(ids)
    lodges=db.scalars(select(Lodge).where((Lodge.id.in_(selected)) | (Lodge.group_id==group.id)).order_by(Lodge.id).with_for_update()).all()
    if selected-{l.id for l in lodges}:raise HTTPException(404,'One or more lodges could not be found')
    if any(l.id in selected and l.group_id not in (None,group.id) for l in lodges):raise HTTPException(409,'A selected lodge already belongs to another group')
    role=db.scalar(select(Role).where(Role.key=='group_admin'))
    for lodge in lodges:
        included=lodge.id in selected
        lodge.group_id=group.id if included else None
        db.flush()
        member=db.scalar(select(Membership).where(Membership.user_id==group.admin_user_id,Membership.lodge_id==lodge.id))
        if member and member.role_id!=role.id:raise HTTPException(409,'This account already has another role in this lodge')
        if included and group.is_active:
            if member:member.is_active=True
            else:db.add(Membership(user_id=group.admin_user_id,lodge_id=lodge.id,role_id=role.id,is_active=True))
        elif member:member.is_active=False
        db.flush()

def serialize(db,group):
    owner=db.get(User,group.admin_user_id)
    return {'id':str(group.id),'name':group.name,'is_active':group.is_active,'administrator':{'id':str(owner.id),'name':owner.full_name,'email':owner.email,**account_email_status(db,owner)},'lodge_ids':[str(i) for i in db.scalars(select(Lodge.id).where(Lodge.group_id==group.id)).all()]}

@router.get('/api/v1/platform/groups')
def groups(actor:User=Depends(require_super_admin),db=Depends(get_db)):
    set_rls_context(db,None,True,str(actor.id))
    return [serialize(db,g) for g in db.scalars(select(LodgeGroup).order_by(LodgeGroup.name)).all()]

@router.post('/api/v1/platform/groups',dependencies=[Depends(require_csrf)])
def create_group(body:GroupCreate,actor:User=Depends(require_super_admin),db=Depends(get_db)):
    set_rls_context(db,None,True,str(actor.id))
    if not body.name.strip():raise HTTPException(422,'Enter a group name')
    owner=db.scalar(select(User).where(func.lower(User.email)==str(body.admin_email).lower()).with_for_update())
    if owner and (owner.is_super_admin or db.scalar(select(Membership.id).join(Role,Role.id==Membership.role_id).where(Membership.user_id==owner.id,Role.key!='group_admin'))):raise HTTPException(409,'Use a separate Group Admin email; this account has another account role')
    if not owner:
        owner=User(email=str(body.admin_email).lower(),full_name=body.admin_name.strip(),password_hash=hash_password(new_token()+new_token()),is_active=False)
        db.add(owner);db.flush()
    group=LodgeGroup(name=body.name.strip(),admin_user_id=owner.id,is_active=True)
    db.add(group);db.flush();sync_lodges(db,group,body.lodge_ids)
    existing_invite=db.scalar(select(Invitation).where(Invitation.user_id==owner.id,Invitation.used_at.is_(None),Invitation.expires_at>datetime.now(timezone.utc))) if not owner.is_active else None
    result=({'delivery_status':account_email_status(db,owner)['delivery_status'],'activation_token':None} if existing_invite else issue_invitation(db,owner,creator_id=actor.id)) if not owner.is_active else {'delivery_status':'already_active','activation_token':None}
    audit(db,actor,'group.created',group.id);db.commit();set_rls_context(db,None,True,str(actor.id))
    return {**serialize(db,group),**result}

@router.patch('/api/v1/platform/groups/{group_id}',dependencies=[Depends(require_csrf)])
def update_group(group_id:uuid.UUID,body:GroupUpdate,actor:User=Depends(require_super_admin),db=Depends(get_db)):
    set_rls_context(db,None,True,str(actor.id))
    group=db.scalar(select(LodgeGroup).where(LodgeGroup.id==group_id).with_for_update())
    if not group:raise HTTPException(404,'Group not found')
    db.scalar(select(User).where(User.id==group.admin_user_id).with_for_update())
    if not body.name.strip():raise HTTPException(422,'Enter a group name')
    group.name=body.name.strip();group.is_active=body.is_active;db.flush();sync_lodges(db,group,body.lodge_ids)
    audit(db,actor,'group.updated',group.id);db.commit();set_rls_context(db,None,True,str(actor.id))
    return serialize(db,group)

@router.get('/api/v1/groups/{group_id}/overview')
def overview(group_id:uuid.UUID,actor:User=Depends(current_user),db=Depends(get_db)):
    group=db.get(LodgeGroup,group_id)
    if not group or not group.is_active or group.admin_user_id!=actor.id:raise HTTPException(403,'You do not have access to this group')
    rows=[];totals={}
    for lodge in db.scalars(select(Lodge).where(Lodge.group_id==group.id).order_by(Lodge.name)).all():
        member=membership_for(db,actor,str(lodge.id))
        if not member:continue
        set_rls_context(db,str(lodge.id),False,str(actor.id))
        sub=db.get(Subscription,lodge.id)
        from .security import subscription_state
        _,status=subscription_state(db,str(lodge.id))
        metrics={}
        try:ensure_subscription_read_allowed(db,str(lodge.id))
        except HTTPException:pass
        else:
            for key,feature,model,extra in [('guest_profiles','guests',Guest,[]),('open_tasks','tasks',Task,[Task.status.notin_(['completed','cancelled'])]),('open_maintenance','maintenance',MaintenanceTicket,[MaintenanceTicket.status.notin_(['completed','closed','resolved','cancelled'])])]:
                permission={'guests':'guests.view','tasks':'tasks.view','maintenance':'maintenance.view'}[feature]
                if entitlement_enabled(db,str(lodge.id),feature) and has_permission(db,member,permission):
                    metrics[key]=db.scalar(select(func.count()).select_from(model).where(model.lodge_id==lodge.id,*extra)) or 0
                    totals[key]=totals.get(key,0)+metrics[key]
        rows.append({'id':str(lodge.id),'name':lodge.brand_name or lodge.name,'location':lodge.location,'package':sub.package if sub else None,'subscription_status':status,'metrics':metrics,'administrators':[{'id':str(u.id),'name':u.full_name,'email':u.email,'access_enabled':m.is_active,**account_email_status(db,u)} for m,u in db.execute(select(Membership,User).join(User,User.id==Membership.user_id).join(Role,Role.id==Membership.role_id).where(Membership.lodge_id==lodge.id,Role.key=='lodge_admin',User.is_super_admin.is_(False))).all()]})
    return {'id':str(group.id),'name':group.name,'lodges':rows,'totals':totals}

@router.post('/api/v1/lodges/{lodge_id}/administrators/invite',dependencies=[Depends(require_csrf)])
def invite_lodge_administrator(lodge_id:str,body:LodgeAdminInvite,actor:User=Depends(require_permission('staff.manage',write=True)),db=Depends(get_db)):
    member=membership_for(db,actor,lodge_id)
    if not member or db.get(Role,member.role_id).key!='group_admin':raise HTTPException(403,'Group Admin access required')
    if db.scalar(select(User.id).where(func.lower(User.email)==str(body.email).lower())):raise HTTPException(409,'Use a separate email for the new Lodge Admin')
    owner=User(email=str(body.email).lower(),full_name=body.full_name.strip(),password_hash=hash_password(new_token()+new_token()),is_active=False)
    db.add(owner);db.flush()
    role=db.scalar(select(Role).where(Role.key=='lodge_admin'))
    db.add(Membership(user_id=owner.id,lodge_id=lodge_id,role_id=role.id,is_active=True));db.flush()
    result=issue_invitation(db,owner,lodge=db.get(Lodge,lodge_id),creator_id=actor.id)
    audit(db,actor,'group.lodge_admin.invited',owner.id,lodge_id,resource_type='user');db.commit()
    return {'id':str(owner.id),**result}


def _group_admin_target(db,actor,lodge_id,user_id):
    member=membership_for(db,actor,lodge_id)
    if not member or db.get(Role,member.role_id).key!='group_admin':raise HTTPException(403,'Group Admin access required')
    target=db.scalar(select(User).where(User.id==user_id,User.is_super_admin.is_(False)).with_for_update())
    role=db.scalar(select(Role).where(Role.key=='lodge_admin'))
    assignment=db.scalar(select(Membership).where(Membership.lodge_id==lodge_id,Membership.user_id==user_id,Membership.role_id==role.id).with_for_update())
    if not target or not assignment:raise HTTPException(404,'Lodge administrator not found')
    return target,assignment

@router.post('/api/v1/lodges/{lodge_id}/administrators/{user_id}/invitation/resend',dependencies=[Depends(require_csrf)])
def resend_lodge_administrator(lodge_id:str,user_id:uuid.UUID,actor:User=Depends(require_permission('staff.manage',write=True)),db=Depends(get_db)):
    target,assignment=_group_admin_target(db,actor,lodge_id,user_id)
    if not assignment.is_active:raise HTTPException(409,'Restore account access before resending an invitation')
    result=issue_invitation(db,target,lodge=db.get(Lodge,lodge_id),creator_id=actor.id)
    audit(db,actor,'group.lodge_admin.invitation_resent',target.id,lodge_id,resource_type='user');db.commit()
    return result

@router.post('/api/v1/lodges/{lodge_id}/administrators/{user_id}/revoke-access',dependencies=[Depends(require_csrf)])
def revoke_lodge_administrator(lodge_id:str,user_id:uuid.UUID,actor:User=Depends(require_permission('staff.manage',write=True)),db=Depends(get_db)):
    from .models import AuthSession,AccountEmail
    target,assignment=_group_admin_target(db,actor,lodge_id,user_id)
    assignment.is_active=False;now=datetime.now(timezone.utc)
    for session in db.scalars(select(AuthSession).where(AuthSession.user_id==target.id,AuthSession.revoked_at.is_(None))).all():session.revoked_at=now
    for inv in db.scalars(select(Invitation).where(Invitation.user_id==target.id,Invitation.used_at.is_(None))).all():inv.used_at=now
    for mail in db.scalars(select(AccountEmail).where(AccountEmail.user_id==target.id,AccountEmail.status.in_(['pending','failed','sending','dead']))).all():mail.status='cancelled';mail.encrypted_payload=None;mail.lease_expires_at=None
    audit(db,actor,'group.lodge_admin.access_revoked',target.id,lodge_id,resource_type='user');db.commit()
    return {'ok':True}

@router.post('/api/v1/lodges/{lodge_id}/administrators/{user_id}/restore-access',dependencies=[Depends(require_csrf)])
def restore_lodge_administrator(lodge_id:str,user_id:uuid.UUID,actor:User=Depends(require_permission('staff.manage',write=True)),db=Depends(get_db)):
    target,assignment=_group_admin_target(db,actor,lodge_id,user_id)
    assignment.is_active=True
    audit(db,actor,'group.lodge_admin.access_restored',target.id,lodge_id,resource_type='user');db.commit()
    return {'ok':True}
