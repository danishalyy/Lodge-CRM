from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pyotp
import pytest
from sqlalchemy import select, text


def test_rls_enforced_without_tenant_and_across_tenants(account):
    from app.models import Guest, Lodge
    from app.db import set_rls_context
    with account['owner']() as db:
        other=Lodge(name='Other '+uuid4().hex);db.add(other);db.flush()
        first=Guest(lodge_id=account['lodge'].id,first_name='Own',last_name='Guest')
        second=Guest(lodge_id=other.id,first_name='Other',last_name='Guest')
        db.add_all([first,second]);db.commit()
    with account['application']() as db:
        assert db.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()==(False,False)
        assert db.scalars(select(Guest)).all()==[]
        set_rls_context(db,str(account['lodge'].id),False)
        assert [row.id for row in db.scalars(select(Guest)).all()]==[first.id]
        assert db.get(Guest,second.id) is None
    client=account['client']
    assert client.get(f'/api/v1/lodges/{other.id}/guests').status_code==403
    assert client.patch(f"/api/v1/lodges/{account['lodge'].id}/guests/{second.id}",json={'notes':'unauthorized'},headers=account['csrf']).status_code==404


def test_csrf_required_for_guest_write(account):
    path=f"/api/v1/lodges/{account['lodge'].id}/guests"
    body={'first_name':'Real','last_name':'Workflow'}
    assert account['client'].post(path,json=body).status_code==403
    response=account['client'].post(path,json=body,headers=account['csrf'])
    assert response.status_code==200,response.text
    assert response.json()['first_name']=='Real'
    assert any(g['id']==response.json()['id'] for g in account['client'].get(path).json())


@pytest.mark.parametrize('state,read_status', [('Expired',200),('Suspended',403),('Pending',403)])
def test_subscription_access_enforced(account,state,read_status):
    from app.models import Subscription
    with account['owner']() as db:
        sub=db.get(Subscription,account['lodge'].id)
        if state=='Expired':sub.start_date=date.today()-timedelta(days=10);sub.expiry_date=date.today()-timedelta(days=1)
        elif state=='Suspended':sub.suspended=True
        else:sub.start_date=date.today()+timedelta(days=1);sub.expiry_date=date.today()+timedelta(days=10)
        db.commit()
    path=f"/api/v1/lodges/{account['lodge'].id}/guests"
    assert account['client'].get(path).status_code==read_status
    assert account['client'].post(path,json={'first_name':'Denied','last_name':'Write'},headers=account['csrf']).status_code==403


def test_read_only_role_cannot_create_guests(account):
    from app.models import Membership,Role
    with account['owner']() as db:
        membership=db.scalar(select(Membership).where(Membership.user_id==account['user'].id))
        membership.role_id=db.scalar(select(Role.id).where(Role.key=='read_only'));db.commit()
    path=f"/api/v1/lodges/{account['lodge'].id}/guests"
    assert account['client'].get(path).status_code==200
    assert account['client'].post(path,json={'first_name':'Denied','last_name':'Role'},headers=account['csrf']).status_code==403


def enable_mfa(account):
    from app.models import User
    from app.security import encrypt_mfa_secret
    secret=pyotp.random_base32()
    with account['owner']() as db:
        user=db.get(User,account['user'].id)
        user.mfa_secret_encrypted=encrypt_mfa_secret(secret)
        user.mfa_enabled_at=datetime.now(timezone.utc);db.commit()
    return secret


def test_enabled_mfa_cannot_be_replaced_by_setup(account):
    from app.models import User
    enable_mfa(account)
    with account['owner']() as db: original=db.get(User,account['user'].id).mfa_secret_encrypted
    assert account['client'].post('/api/v1/auth/mfa/setup',headers=account['csrf']).status_code==409
    with account['owner']() as db:
        user=db.get(User,account['user'].id)
        assert user.mfa_enabled_at is not None
        assert user.mfa_secret_encrypted==original


def test_mfa_disable_requires_password_and_code(account):
    secret=enable_mfa(account)
    path='/api/v1/auth/mfa/disable'
    code=pyotp.TOTP(secret).now()
    assert account['client'].post(path,json={'code':code},headers=account['csrf']).status_code==422
    assert account['client'].post(path,json={'code':code,'current_password':'incorrect'},headers=account['csrf']).status_code==403
    result=account['client'].post(path,json={'code':code,'current_password':account['password']},headers=account['csrf'])
    assert result.status_code==200,result.text
    assert result.json()=={'enabled':False}


def test_password_reset_revokes_sessions_without_bypassing_mfa(account):
    from app.models import PasswordResetToken,AuthSession
    from app.security import token_hash, new_token
    enable_mfa(account)
    token=new_token();password='New-Production-Password-934!'
    with account['owner']() as db:
        db.add(PasswordResetToken(user_id=account['user'].id,token_hash=token_hash(token),expires_at=datetime.now(timezone.utc)+timedelta(minutes=10)));db.commit()
    client=account['client']
    result=client.post('/api/v1/auth/password-reset/confirm',json={'token':token,'password':password})
    assert result.status_code==200,result.text
    assert client.get('/api/v1/auth/me').status_code==401
    with account['owner']() as db:
        assert db.scalars(select(AuthSession).where(AuthSession.user_id==account['user'].id,AuthSession.revoked_at.is_(None))).all()==[]
    response=client.post('/api/v1/auth/login',json={'email':account['user'].email,'password':password})
    assert response.status_code==401
    assert response.json()['detail']=='MFA_REQUIRED'
    assert client.post('/api/v1/auth/password-reset/confirm',json={'token':token,'password':password}).status_code==400


def test_mfa_login_rejects_reused_code(account):
    secret=enable_mfa(account)
    body={'email':account['user'].email,'password':account['password'],'otp':pyotp.TOTP(secret).now()}
    client=account['client']
    assert client.post('/api/v1/auth/login',json=body).status_code==200
    response=client.post('/api/v1/auth/login',json=body)
    assert response.status_code==401
    assert response.json()['detail']=='Invalid or already-used MFA code'


def test_reset_token_consumed_once_under_concurrent_requests(account):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from app.main import app
    from app.models import PasswordResetToken
    from app.security import token_hash,new_token
    token=new_token()
    with account['owner']() as db:
        db.add(PasswordResetToken(user_id=account['user'].id,token_hash=token_hash(token),expires_at=datetime.now(timezone.utc)+timedelta(minutes=10)));db.commit()
    barrier=Barrier(2)
    def reset():
        client=TestClient(app)
        try:
            barrier.wait(timeout=10)
            return client.post('/api/v1/auth/password-reset/confirm',json={'token':token,'password':'Concurrent-Secure-Password-729!'}).status_code
        finally:client.close()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures=[executor.submit(reset) for _ in range(2)]
        assert sorted(f.result(timeout=30) for f in futures)==[200,400]
