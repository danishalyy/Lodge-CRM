"""Identity separation with real sessions, RLS, and HTTP dependencies."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import ast
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select


def other_account(account, *, lodge_id=None, active=True, platform=False):
    from app.models import User,Membership,Role,AuthSession
    from app.security import new_token,token_hash
    raw,csrf=new_token(),new_token()
    with account['owner']() as db:
        user=User(email=uuid4().hex+'@example.com',full_name='Other Account',password_hash=account['user'].password_hash,is_active=active,is_super_admin=platform)
        db.add(user);db.flush()
        if lodge_id:
            role=db.scalar(select(Role).where(Role.key=='lodge_admin'))
            db.add(Membership(user_id=user.id,lodge_id=lodge_id,role_id=role.id))
        session=AuthSession(user_id=user.id,token_hash=token_hash(raw),csrf_hash=token_hash(csrf),expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
        db.add(session);db.commit()
    return user,session,raw,csrf


def test_sessions_are_private_and_cannot_be_revoked_by_another_user(account):
    from app.models import AuthSession
    user,session,raw,csrf=other_account(account,lodge_id=account['lodge'].id)
    rows=account['client'].get('/api/v1/auth/sessions').json()
    assert rows and str(session.id) not in {r['id'] for r in rows}
    assert account['client'].delete('/api/v1/auth/sessions/'+str(session.id),headers=account['csrf']).status_code==404
    with account['owner']() as db:assert db.get(AuthSession,session.id).revoked_at is None
    # Another user's CSRF token cannot authorize this session.
    assert account['client'].post('/api/v1/auth/logout',headers={'X-CSRF-Token':csrf}).status_code==403
    assert account['client'].get('/api/v1/auth/me').json()['id']==str(account['user'].id)


def test_stale_tab_cannot_act_as_another_logged_in_account(account):
    client=account['client']
    assert client.get('/api/v1/auth/me',headers={'X-Expected-User-Id':str(uuid4())}).status_code==409
    assert client.get('/api/v1/auth/me',headers={'X-Expected-User-Id':str(account['user'].id)}).status_code==200
    path=f"/api/v1/lodges/{account['lodge'].id}/guests"
    assert client.post(path,json={'first_name':'Must','last_name':'Not Persist'},headers={**account['csrf'],'X-Expected-User-Id':str(uuid4())}).status_code==409


@pytest.mark.parametrize('state',['expired','revoked','inactive','membership-revoked'])
def test_unusable_account_session_cannot_access_profile(account,state):
    from app.models import User,AuthSession,Membership
    from app.security import token_hash
    with account['owner']() as db:
        session=db.scalar(select(AuthSession).where(AuthSession.token_hash==token_hash(account['client'].cookies['lodge_session'])))
        if state=='expired':session.expires_at=datetime.now(timezone.utc)-timedelta(seconds=1)
        elif state=='revoked':session.revoked_at=datetime.now(timezone.utc)
        elif state=='inactive':db.get(User,account['user'].id).is_active=False
        else:db.scalar(select(Membership).where(Membership.user_id==account['user'].id)).is_active=False
        db.commit()
    assert account['client'].get('/api/v1/auth/me').status_code==401
    assert account['client'].get('/api/v1/auth/sessions').status_code==401


def test_mfa_required_for_platform_users_on_lodge_routes(account):
    from app.main import app
    user,session,raw,csrf=other_account(account,platform=True)
    client=TestClient(app)
    try:
        client.cookies.set('lodge_session',raw)
        path=f"/api/v1/lodges/{account['lodge'].id}/guests"
        response=client.get(path)
        assert response.status_code==403
        assert response.json()['detail']=='Super Admin MFA setup is required'
    finally:client.close()


@pytest.mark.parametrize('active',[False,True])
def test_inviting_foreign_account_cannot_attach_it_to_another_lodge(account,active):
    from app.models import Lodge,StaffProfile,Membership
    with account['owner']() as db:
        foreign=Lodge(name='Foreign '+uuid4().hex);db.add(foreign);db.commit()
    foreign_user,*_=other_account(account,lodge_id=foreign.id,active=active)
    with account['owner']() as db:
        staff=StaffProfile(lodge_id=account['lodge'].id,full_name='Foreign Email',email=foreign_user.email)
        db.add(staff);db.commit()
    response=account['client'].post(f"/api/v1/lodges/{account['lodge'].id}/staff/{staff.id}/invite",json={'role_key':'general_staff'},headers=account['csrf'])
    assert response.status_code==409,response.text
    with account['owner']() as db:
        assert db.get(StaffProfile,staff.id).user_id is None
        assert db.scalars(select(Membership).where(Membership.user_id==foreign_user.id)).one().lodge_id==foreign.id


def test_notifications_cannot_be_read_or_marked_by_other_lodge_user(account):
    from app.models import Notification,NotificationRecipient
    user,*_=other_account(account,lodge_id=account['lodge'].id)
    with account['owner']() as db:
        notification=Notification(lodge_id=account['lodge'].id,notification_type='private.test',title='Private recipient',body='Not for the requester')
        db.add(notification);db.flush()
        recipient=NotificationRecipient(lodge_id=account['lodge'].id,notification_id=notification.id,user_id=user.id)
        db.add(recipient);db.commit()
    path=f"/api/v1/lodges/{account['lodge'].id}/notifications"
    assert str(notification.id) not in {x['id'] for x in account['client'].get(path).json()}
    assert account['client'].post(path+'/'+str(notification.id)+'/read',headers=account['csrf']).status_code==404
    with account['owner']() as db:assert db.get(NotificationRecipient,recipient.id).read_at is None


def test_every_tenant_route_denies_another_lodge(account):
    from app.models import Lodge
    with account['owner']() as db:
        foreign=Lodge(name='Foreign Route Matrix '+uuid4().hex);db.add(foreign);db.commit()
    tree=ast.parse((Path(__file__).resolve().parents[2]/'app/main.py').read_text())
    checked=[]
    for fn in tree.body:
        if not isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
        for dec in fn.decorator_list:
            if not (isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute) and isinstance(dec.func.value,ast.Name) and dec.func.value.id=='app'):continue
            method=dec.func.attr.upper()
            if method not in {'GET','POST','PATCH','DELETE','PUT'}:continue
            path=ast.literal_eval(dec.args[0])
            if not path.startswith('/api/v1/lodges/{lodge_id}/'):continue
            path=path.replace('{lodge_id}',str(foreign.id))
            path=re.sub(r'\{[^}]+\}',str(uuid4()),path)
            response=account['client'].request(method,path,json={},headers=account['csrf'])
            assert response.status_code==403,(method,path,response.status_code,response.text)
            checked.append((method,path))
    assert len(checked)>90
    print(f'Cross-lodge authorization verified on {len(checked)} tenant routes')


def test_staff_cannot_read_or_change_another_staff_members_tasks(account):
    from app.models import Role,Membership,StaffProfile,Task
    with account['owner']() as db:
        m=db.scalar(select(Membership).where(Membership.user_id==account['user'].id))
        m.role_id=db.scalar(select(Role.id).where(Role.key=='general_staff'))
        own=StaffProfile(lodge_id=account['lodge'].id,full_name='Own Staff',user_id=account['user'].id)
        other=StaffProfile(lodge_id=account['lodge'].id,full_name='Other Staff')
        db.add_all([own,other]);db.flush()
        own_task=Task(lodge_id=account['lodge'].id,title='Own task',assigned_staff_id=own.id,created_by_user_id=account['user'].id,status='assigned')
        other_task=Task(lodge_id=account['lodge'].id,title='Other task',assigned_staff_id=other.id,created_by_user_id=account['user'].id,status='assigned')
        db.add_all([own_task,other_task]);db.commit()
    path=f"/api/v1/lodges/{account['lodge'].id}/tasks"
    result=account['client'].get(path)
    assert result.status_code==200,result.text
    ids={t['id'] for t in result.json()}
    assert str(own_task.id) in ids and str(other_task.id) not in ids
    assert account['client'].patch(path+'/'+str(own_task.id),json={'status':'accepted'},headers=account['csrf']).status_code==200
    for suffix in ['checklist','comments','attachments']:
        assert account['client'].get(path+'/'+str(other_task.id)+'/'+suffix).status_code==403
    assert account['client'].patch(path+'/'+str(other_task.id),json={'status':'accepted'},headers=account['csrf']).status_code==403


def test_database_rejects_second_lodge_for_same_login(account):
    from app.models import Lodge,Membership,Role
    from sqlalchemy.exc import IntegrityError
    with account['owner']() as db:
        foreign=Lodge(name='Second Membership '+uuid4().hex);db.add(foreign);db.commit()
        role=db.scalar(select(Role).where(Role.key=='lodge_admin'))
        db.add(Membership(user_id=account['user'].id,lodge_id=foreign.id,role_id=role.id))
        with pytest.raises(IntegrityError) as error:
            db.commit()
        assert error.value.orig.diag.constraint_name=='uq_membership_one_lodge_per_user'
        db.rollback()
        assert len(db.scalars(select(Membership).where(Membership.user_id==account['user'].id)).all())==1
    assert account['client'].get('/api/v1/auth/me').status_code==200


def test_department_manager_cannot_read_or_edit_another_departments_hr(account):
    from datetime import date
    from app.models import Department,StaffProfile,Membership,Role,StaffLeave
    with account['owner']() as db:
        own=Department(lodge_id=account['lodge'].id,name='Own Department')
        other=Department(lodge_id=account['lodge'].id,name='Other Department')
        db.add_all([own,other]);db.flush()
        m=db.scalar(select(Membership).where(Membership.user_id==account['user'].id))
        m.role_id=db.scalar(select(Role.id).where(Role.key=='department_manager'));m.department_id=own.id
        staff=StaffProfile(lodge_id=account['lodge'].id,full_name='Other Department Staff',department_id=other.id)
        db.add(staff);db.flush()
        leave=StaffLeave(lodge_id=account['lodge'].id,staff_id=staff.id,leave_type='annual',start_date=date.today(),end_date=date.today()+timedelta(days=1),status='pending')
        db.add(leave);db.commit()
    path=f"/api/v1/lodges/{account['lodge'].id}/hr/leaves"
    result=account['client'].get(path)
    assert result.status_code==200,result.text
    assert str(leave.id) not in {x['id'] for x in result.json()}
    assert account['client'].patch(path+'/'+str(leave.id),json={'status':'approved'},headers=account['csrf']).status_code==403


def test_logout_revokes_the_server_session(account):
    from app.main import app
    raw=account['client'].cookies['lodge_session']
    assert account['client'].post('/api/v1/auth/logout',headers=account['csrf']).status_code==200
    assert account['client'].get('/api/v1/auth/me').status_code==401
    replay=TestClient(app)
    try:
        replay.cookies.set('lodge_session',raw)
        assert replay.get('/api/v1/auth/me').status_code==401
    finally:replay.close()


def test_password_change_revokes_own_other_sessions_without_touching_other_users(account):
    from app.models import AuthSession
    from app.security import new_token,token_hash
    user,foreign_session,*_=other_account(account,lodge_id=account['lodge'].id)
    with account['owner']() as db:
        own_other=AuthSession(user_id=account['user'].id,token_hash=token_hash(new_token()),csrf_hash=token_hash(new_token()),expires_at=datetime.now(timezone.utc)+timedelta(hours=1))
        db.add(own_other);db.commit()
    result=account['client'].post('/api/v1/auth/change-password',headers=account['csrf'],json={'current_password':account['password'],'new_password':'New-Own-Password-7284!'})
    assert result.status_code==200,result.text
    assert account['client'].get('/api/v1/auth/me').status_code==200
    with account['owner']() as db:
        assert db.get(AuthSession,own_other.id).revoked_at is not None
        assert db.get(AuthSession,foreign_session.id).revoked_at is None


def test_configured_frontend_can_send_expected_identity_header(api):
    response=api[0].options('/api/v1/auth/me',headers={'Origin':'http://localhost:3000','Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'X-Expected-User-Id'})
    assert response.status_code==200
    assert 'x-expected-user-id' in response.headers['access-control-allow-headers'].lower()


def test_activation_token_is_consumed_once_during_concurrent_requests(account):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.main import app
    from app.models import Invitation
    from app.security import new_token,token_hash
    user,*_=other_account(account,lodge_id=account['lodge'].id,active=False)
    token=new_token()
    with account['owner']() as db:
        db.add(Invitation(lodge_id=account['lodge'].id,user_id=user.id,token_hash=token_hash(token),expires_at=datetime.now(timezone.utc)+timedelta(hours=1),created_by_user_id=account['user'].id));db.commit()
    barrier=Barrier(2)
    def activate():
        client=TestClient(app)
        try:
            barrier.wait(timeout=10)
            return client.post('/api/v1/auth/activate',json={'token':token,'password':'Activated-Account-7295!'}).status_code
        finally:client.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(activate) for _ in range(2)]
        assert sorted(f.result(timeout=30) for f in futures)==[200,400]
