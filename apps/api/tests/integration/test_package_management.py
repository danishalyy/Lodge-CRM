from datetime import datetime,timezone
from uuid import uuid4
from sqlalchemy import select


def promote(account):
    from app.models import User,AuthSession
    with account['owner']() as db:
        user=db.get(User,account['user'].id);user.is_super_admin=True;user.mfa_enabled_at=datetime.now(timezone.utc)
        session=db.scalar(select(AuthSession).where(AuthSession.user_id==user.id));session.mfa_verified_at=datetime.now(timezone.utc);db.commit()


def test_plan_edit_is_super_only_csrf_protected_and_immediate(account):
    from app.models import PlanEntitlement,Plan,AuditLog,User,LodgeEntitlementOverride
    from app.security import entitlement_enabled
    from app.db import set_rls_context
    c=account['client'];path='/api/v1/platform/plans/Standard'
    assert c.patch(path,json={'features':[],'expected_revision':1,'expected_lodge_count':0},headers=account['csrf']).status_code==403
    with account['owner']() as db:
        db.get(User,account['user'].id).is_super_admin=True;db.commit()
    assert c.patch(path,json={'features':[],'expected_revision':1,'expected_lodge_count':0},headers=account['csrf']).status_code==403
    promote(account)
    with account['owner']() as db:
        db.add(LodgeEntitlementOverride(lodge_id=account['lodge'].id,feature_key='guests',enabled=False,reason='Private lodge exception'));db.commit()
    plans=c.get('/api/v1/platform/plans').json();plan=next(p for p in plans if p['key']=='Standard')
    assert plan['description'] and plan['lodge_count']>=1
    assert next(f for f in plan['feature_catalog'] if f['key']=='telemetry')['status']=='coming_soon'
    assert 'telemetry' not in plan['features']
    original=list(plan['features']);features=[key for key in original if key!='fuel']
    payload={'features':features,'expected_revision':plan['revision'],'expected_lodge_count':plan['lodge_count']}
    assert c.patch(path,json=payload).status_code==403
    assert c.patch(path,json={**payload,'expected_lodge_count':-1},headers=account['csrf']).status_code==422
    assert c.patch(path,json={**payload,'expected_lodge_count':plan['lodge_count']+1},headers=account['csrf']).status_code==409
    assert c.patch(path,json={**payload,'features':features+['telemetry']},headers=account['csrf']).status_code==422
    try:
        result=c.patch(path,json=payload,headers=account['csrf']);assert result.status_code==200,result.text
        updated=result.json();assert updated['revision']==plan['revision']+1 and updated['lodge_count']==plan['lodge_count']
        with account['application']() as db:
            set_rls_context(db,str(account['lodge'].id),False,str(account['user'].id))
            assert not entitlement_enabled(db,str(account['lodge'].id),'fuel')
            assert not entitlement_enabled(db,str(account['lodge'].id),'guests')
            assert db.get(LodgeEntitlementOverride,{'lodge_id':account['lodge'].id,'feature_key':'guests'}).reason=='Private lodge exception'
        assert c.patch(path,json=payload,headers=account['csrf']).status_code==409
        with account['owner']() as db:assert db.scalar(select(AuditLog).where(AuditLog.action=='plan.updated',AuditLog.resource_id=='Standard'))
    finally:
        # Shared seeded plans must be restored for unrelated integration tests.
        with account['owner']() as db:
            for row in db.scalars(select(PlanEntitlement).where(PlanEntitlement.plan_key=='Standard')):
                if row.feature_key in {f['key'] for f in plan['feature_catalog'] if f['available']}:row.enabled=row.feature_key in original
            db.commit()


def test_lodge_exception_requires_reason_and_preserves_plan(account):
    from app.models import LodgeEntitlementOverride,PlanEntitlement,AuditLog
    promote(account);c=account['client'];path=f"/api/v1/platform/lodges/{account['lodge'].id}/entitlements"
    assert c.patch(path,json={'feature_key':'fuel','enabled':False},headers=account['csrf']).status_code==422
    response=c.patch(path,json={'feature_key':'fuel','enabled':False,'reason':'Owner requested fuel exclusion'},headers=account['csrf']);assert response.status_code==200,response.text
    assert 'fuel' in response.json()['base'] and 'fuel' not in response.json()['effective']
    override=next(o for o in response.json()['overrides'] if o['feature_key']=='fuel');assert override['reason']=='Owner requested fuel exclusion'
    assert c.patch(path,json={'feature_key':'telemetry','enabled':True,'reason':'Attempt future feature'},headers=account['csrf']).status_code==422
    response=c.patch(path,json={'feature_key':'fuel','enabled':None,'reason':'Restore plan default'},headers=account['csrf']);assert 'fuel' in response.json()['effective']
    with account['owner']() as db:assert db.scalar(select(AuditLog).where(AuditLog.action=='entitlement.override',AuditLog.detail.contains('Restore plan default')))


def test_access_review_notifies_platform_and_blocks_cross_lodge(account):
    from app.models import User,Lodge,Notification,NotificationRecipient
    c=account['client'];base=f"/api/v1/lodges/{account['lodge'].id}"
    with account['owner']() as db:
        platform=User(email=uuid4().hex+'@example.com',full_name='Platform recipient',password_hash=account['user'].password_hash,is_super_admin=True)
        other=Lodge(name='Other package '+uuid4().hex);db.add_all([platform,other]);db.commit()
    info=c.get(base+'/feature-access?feature_key=custom_roles');assert info.status_code==200 and info.json()['available']
    future=c.get(base+'/feature-access?feature_key=telemetry').json();assert future['status']=='coming_soon' and not future['unlocking_plans']
    assert c.post(f'/api/v1/lodges/{other.id}/access-reviews',json={'feature_key':'telemetry'},headers=account['csrf']).status_code==403
    assert c.get(f'/api/v1/lodges/{other.id}/feature-access?feature_key=fuel').status_code==403
    assert c.post(base+'/access-reviews',json={'feature_key':'telemetry'}).status_code==403
    result=c.post(base+'/access-reviews',json={'feature_key':'telemetry','reason':'Please discuss vehicle tracking'},headers=account['csrf']);assert result.status_code==200,result.text
    assert not result.json()['already_pending']
    assert c.post(base+'/access-reviews',json={'feature_key':'telemetry'},headers=account['csrf']).json()['already_pending']
    with account['owner']() as db:
        notices=db.scalars(select(Notification).where(Notification.lodge_id==account['lodge'].id,Notification.notification_type=='feature.access_review')).all();assert len(notices)==1
        recipients=db.scalars(select(NotificationRecipient).where(NotificationRecipient.notification_id==notices[0].id)).all();assert str(platform.id) in [str(r.user_id) for r in recipients]
