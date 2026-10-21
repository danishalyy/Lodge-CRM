"""Group access remains explicitly scoped, including database and invitation paths."""
from datetime import date,datetime,timedelta,timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models import User,Lodge,Subscription,Membership,Role,Guest,LodgeGroup,LodgeEntitlementOverride
from app.security import hash_password

@pytest.fixture
def group(account):
    from app.main import app
    with account['owner']() as db:
        actor=db.get(User,account['user'].id);actor.is_super_admin=True;actor.mfa_enabled_at=datetime.now(timezone.utc)
        second=Lodge(name='Second lodge '+uuid4().hex);foreign=Lodge(name='Private foreign '+uuid4().hex)
        db.add_all([second,foreign]);db.flush()
        for l in [second,foreign]:db.add(Subscription(lodge_id=l.id,package='Basic',start_date=date.today()-timedelta(days=1),expiry_date=date.today()+timedelta(days=90)))
        db.commit()
    email=f'{uuid4().hex}@example.com'
    result=account['client'].post('/api/v1/platform/groups',json={'name':'Owner group '+uuid4().hex,'admin_name':'Multi Lodge Owner','admin_email':email,'lodge_ids':[str(account['lodge'].id),str(second.id)]},headers=account['csrf'])
    assert result.status_code==200,result.text
    client=TestClient(app)
    token=result.json()['activation_token']
    response=client.post('/api/v1/auth/activate',json={'token':token,'password':'Private group owner passphrase 42!'})
    assert response.status_code==200,response.text
    yield {**account,'group_client':client,'group':result.json(),'second':second,'foreign':foreign,'email':email,'group_csrf':{'X-CSRF-Token':client.cookies['lodge_csrf']}}
    client.close()


def test_group_admin_can_sign_in_and_switch_only_assigned_lodges(group):
    c=group['group_client'];c.cookies.clear()
    assert c.post('/api/v1/auth/login',json={'email':group['email'],'password':'Private group owner passphrase 42!'}).status_code==200
    me=c.get('/api/v1/auth/me').json()
    assert len(me['memberships'])==2 and len(me['groups'])==1 and not me['is_super_admin']
    assert all(m['role_key']=='group_admin' for m in me['memberships'])
    for lid in [group['lodge'].id,group['second'].id]:assert c.get(f'/api/v1/lodges/{lid}/guests').status_code==200
    assert c.get(f"/api/v1/lodges/{group['foreign'].id}/guests").status_code==403
    assert c.get('/api/v1/platform/users').status_code==403
    assert c.get('/api/v1/platform/groups').status_code==403
    assert c.get('/api/v1/auth/me',headers={'X-Lodge-Context':str(group['foreign'].id)}).status_code==403


def test_group_overview_excludes_foreign_and_disabled_metrics(group):
    with group['owner']() as db:
        for lodge,name in [(group['lodge'],'First'),(group['second'],'Second'),(group['foreign'],'Hidden')]:db.add(Guest(lodge_id=lodge.id,first_name=name,last_name='Guest'))
        db.add(LodgeEntitlementOverride(lodge_id=group['second'].id,feature_key='guests',enabled=False));db.commit()
    result=group['group_client'].get(f"/api/v1/groups/{group['group']['id']}/overview")
    assert result.status_code==200,result.text
    data=result.json()
    assert {l['id'] for l in data['lodges']}=={str(group['lodge'].id),str(group['second'].id)}
    assert data['totals']['guest_profiles']==1
    assert 'guest_profiles' not in next(l for l in data['lodges'] if l['id']==str(group['second'].id))['metrics']
    assert group['group_client'].get(f'/api/v1/groups/{uuid4()}/overview').status_code==403


def test_detaching_lodge_revokes_access_without_affecting_local_admin(group):
    gid=group['group']['id']
    response=group['client'].patch(f'/api/v1/platform/groups/{gid}',json={'name':group['group']['name'],'lodge_ids':[str(group['lodge'].id)],'is_active':True},headers=group['csrf'])
    assert response.status_code==200,response.text
    assert group['group_client'].get(f"/api/v1/lodges/{group['second'].id}/guests").status_code==403
    me=group['group_client'].get('/api/v1/auth/me').json()
    assert len(me['memberships'])==1
    with group['owner']() as db:
        assert db.scalar(select(Membership).where(Membership.user_id==group['user'].id)).is_active


def test_suspending_group_revokes_existing_session_and_can_restore(group):
    gid=group['group']['id'];body={'name':group['group']['name'],'lodge_ids':group['group']['lodge_ids'],'is_active':False}
    assert group['client'].patch(f'/api/v1/platform/groups/{gid}',json=body,headers=group['csrf']).status_code==200
    assert group['group_client'].get('/api/v1/auth/me').status_code==401
    body['is_active']=True
    assert group['client'].patch(f'/api/v1/platform/groups/{gid}',json=body,headers=group['csrf']).status_code==200
    assert group['group_client'].get('/api/v1/auth/me').status_code==200


def test_group_admin_invites_separate_lodge_admin_without_platform_privileges(group):
    lid=group['lodge'].id;client=group['group_client']
    response=client.post(f'/api/v1/lodges/{lid}/administrators/invite',json={'full_name':'Local Lodge Owner','email':f'{uuid4().hex}@gmail.com'},headers=group['group_csrf'])
    assert response.status_code==200,response.text
    from app.main import app
    local=TestClient(app)
    try:
        assert local.post('/api/v1/auth/activate',json={'token':response.json()['activation_token'],'password':'Private local owner passphrase 42!'}).status_code==200
        me=local.get('/api/v1/auth/me').json()
        assert not me['groups'] and len(me['memberships'])==1 and me['memberships'][0]['role_key']=='lodge_admin'
        assert local.get(f"/api/v1/lodges/{group['second'].id}/guests").status_code==403
        assert local.get(f"/api/v1/groups/{group['group']['id']}/overview").status_code==403
    finally:local.close()


def test_database_blocks_forged_group_membership(group):
    with group['owner']() as db:
        owner_id=group['group']['administrator']['id']
        role=db.scalar(select(Role).where(Role.key=='group_admin'))
        db.add(Membership(user_id=owner_id,lodge_id=group['foreign'].id,role_id=role.id))
        with pytest.raises(IntegrityError) as error:db.commit()
        assert error.value.orig.diag.constraint_name=='ck_membership_group_assignment'


def test_group_lodge_cannot_be_stolen_by_another_group(group):
    result=group['client'].post('/api/v1/platform/groups',json={'name':'Another group '+uuid4().hex,'admin_name':'Another Owner','admin_email':f'{uuid4().hex}@example.com','lodge_ids':[str(group['lodge'].id)]},headers=group['csrf'])
    assert result.status_code==409
    with group['owner']() as db:assert str(db.get(Lodge,group['lodge'].id).group_id)==group['group']['id']


def test_group_subscriptions_and_foreign_group_rows_remain_isolated(group):
    result=group['client'].post('/api/v1/platform/groups',json={'name':'Foreign group '+uuid4().hex,'admin_name':'Other Owner','admin_email':f'{uuid4().hex}@example.com','lodge_ids':[str(group['foreign'].id)]},headers=group['csrf'])
    assert result.status_code==200,result.text
    assert group['group_client'].get(f"/api/v1/groups/{result.json()['id']}/overview").status_code==403
    me=group['group_client'].get('/api/v1/auth/me').json()
    by_id={m['lodge_id']:m for m in me['memberships']}
    assert 'staff_hr' in by_id[str(group['lodge'].id)]['entitlements']
    assert 'staff_hr' not in by_id[str(group['second'].id)]['entitlements']
    from app.db import set_rls_context
    with group['application']() as db:
        set_rls_context(db,None,False,group['group']['administrator']['id'])
        assert {str(g.id) for g in db.scalars(select(LodgeGroup)).all()}=={group['group']['id']}
    denied=group['group_client'].post(f"/api/v1/lodges/{group['foreign'].id}/administrators/invite",json={'full_name':'Denied Owner','email':f'{uuid4().hex}@example.com'},headers=group['group_csrf'])
    assert denied.status_code==403


def test_pending_group_owner_can_receive_more_groups_without_replacing_setup_link(account):
    with account['owner']() as db:
        actor=db.get(User,account['user'].id);actor.is_super_admin=True;actor.mfa_enabled_at=datetime.now(timezone.utc);db.commit()
    body={'name':'First empty '+uuid4().hex,'admin_name':'Pending Owner','admin_email':f'{uuid4().hex}@example.com','lodge_ids':[]}
    first=account['client'].post('/api/v1/platform/groups',json=body,headers=account['csrf']);assert first.status_code==200,first.text
    body['name']='Second empty '+uuid4().hex
    second=account['client'].post('/api/v1/platform/groups',json=body,headers=account['csrf']);assert second.status_code==200,second.text
    assert second.json()['administrator']['id']==first.json()['administrator']['id'] and second.json()['activation_token'] is None
    from app.main import app
    client=TestClient(app)
    try:
        assert client.post('/api/v1/auth/activate',json={'token':first.json()['activation_token'],'password':'Pending owner private passphrase 42!'}).status_code==200
        me=client.get('/api/v1/auth/me').json();assert len(me['groups'])==2 and not me['memberships']
    finally:client.close()


def test_group_admin_resends_revokes_and_restores_local_admin_access(group):
    from app.models import Invitation
    from app.main import app
    client=group['group_client'];lid=group['lodge'].id;email=f'{uuid4().hex}@example.com'
    response=client.post(f'/api/v1/lodges/{lid}/administrators/invite',json={'full_name':'Managed Local Admin','email':email},headers=group['group_csrf'])
    assert response.status_code==200,response.text
    user_id=response.json()['id'];old_token=response.json()['activation_token']
    path=f'/api/v1/lodges/{lid}/administrators/{user_id}'
    assert client.post(path+'/invitation/resend',headers=group['group_csrf']).status_code==429
    with group['owner']() as db:
        db.get(Invitation,response.json()['invitation_id']).created_at-=timedelta(minutes=2);db.commit()
    resend=client.post(path+'/invitation/resend',headers=group['group_csrf']);assert resend.status_code==200,resend.text
    assert client.post('/api/v1/auth/invitations/preview',json={'token':old_token}).status_code==400
    local=TestClient(app)
    try:
        assert local.post('/api/v1/auth/activate',json={'token':resend.json()['activation_token'],'password':'Local admin private passphrase 42!'}).status_code==200
        assert client.post(path+'/revoke-access',headers=group['group_csrf']).status_code==200
        assert local.get('/api/v1/auth/me').status_code==401
        data=client.get(f"/api/v1/groups/{group['group']['id']}/overview").json()
        admin=next(a for l in data['lodges'] if l['id']==str(lid) for a in l['administrators'] if a['id']==user_id)
        assert not admin['access_enabled']
        assert client.post(path+'/restore-access',headers=group['group_csrf']).status_code==200
        assert local.get('/api/v1/auth/me').status_code==401, 'Restoration must not revive revoked sessions'
        local.cookies.clear()
        assert local.post('/api/v1/auth/login',json={'email':email,'password':'Local admin private passphrase 42!'}).status_code==200
        assert local.get(f'/api/v1/lodges/{lid}/guests').status_code==200
        assert local.get(f"/api/v1/lodges/{group['second'].id}/guests").status_code==403
        assert client.post(f"/api/v1/lodges/{lid}/administrators/{group['group']['administrator']['id']}/revoke-access",headers=group['group_csrf']).status_code==404
    finally:local.close()


def test_suspending_one_group_keeps_other_owned_groups_available(group):
    result=group['client'].post('/api/v1/platform/groups',json={'name':'Another owned group '+uuid4().hex,'admin_name':'Existing Owner','admin_email':group['email'],'lodge_ids':[str(group['foreign'].id)]},headers=group['csrf'])
    assert result.status_code==200,result.text
    gid=group['group']['id']
    response=group['client'].patch(f'/api/v1/platform/groups/{gid}',json={'name':group['group']['name'],'lodge_ids':group['group']['lodge_ids'],'is_active':False},headers=group['csrf'])
    assert response.status_code==200,response.text
    me=group['group_client'].get('/api/v1/auth/me')
    assert me.status_code==200,me.text
    assert [g['id'] for g in me.json()['groups']]==[result.json()['id']]
    assert group['group_client'].get(f"/api/v1/lodges/{group['foreign'].id}/guests").status_code==200
    assert group['group_client'].get(f"/api/v1/lodges/{group['lodge'].id}/guests").status_code==403


def test_disabled_report_features_are_omitted_from_json_and_csv(account):
    with account['owner']() as db:
        for feature in ['tasks','fuel','wildlife']:
            db.add(LodgeEntitlementOverride(lodge_id=account['lodge'].id,feature_key=feature,enabled=False))
        db.commit()
    path=f"/api/v1/lodges/{account['lodge'].id}/reports/summary"
    result=account['client'].get(path);assert result.status_code==200,result.text
    body=result.json();assert body['tasks'] is None and body['fleet'] is None and body['safari']['wildlife_sightings'] is None
    exported=account['client'].get(path+'.csv');assert exported.status_code==200
    assert 'fuel_litres' not in exported.text and '"tasks","created"' not in exported.text
