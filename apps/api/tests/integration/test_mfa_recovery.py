from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pyotp
from sqlalchemy import select


def enroll(account):
    client=account['client']
    response=client.post('/api/v1/auth/mfa/setup',headers=account['csrf'])
    assert response.status_code==200,response.text
    setup=response.json()
    assert setup['otpauth_uri'].startswith('otpauth://totp/')
    code=pyotp.TOTP(setup['secret']).now()
    response=client.post('/api/v1/auth/mfa/confirm',json={'code':code},headers=account['csrf'])
    assert response.status_code==200,response.text
    codes=response.json()['recovery_codes']
    assert len(codes)==len(set(codes))==10
    return setup,codes


def test_recovery_codes_hashed_private_once_and_require_password(account):
    from app.models import User,AuditLog
    setup,codes=enroll(account)
    with account['owner']() as db:
        user=db.get(User,account['user'].id)
        assert len(user.mfa_recovery_hashes)==10
        assert not any(code in str(user.mfa_recovery_hashes) for code in codes)
        assert all(len(value)==64 for value in user.mfa_recovery_hashes)
        audit=db.scalar(select(AuditLog).where(AuditLog.actor_user_id==user.id,AuditLog.action=='mfa.enabled'))
        assert audit and not any(code in audit.detail for code in codes)
    assert 'recovery_codes' not in account['client'].get('/api/v1/auth/me').json()
    body={'email':account['user'].email,'password':'Wrong-password-123','recovery_code':codes[0]}
    assert account['client'].post('/api/v1/auth/login',json=body).status_code==401
    body['password']=account['password']
    assert account['client'].post('/api/v1/auth/login',json=body).status_code==200
    assert account['client'].post('/api/v1/auth/login',json=body).status_code==401
    with account['owner']() as db:assert len(db.get(User,account['user'].id).mfa_recovery_hashes)==9


def test_mfa_recovery_requires_csrf_and_regeneration_reauthentication(account):
    from app.models import User
    setup,codes=enroll(account)
    client=account['client'];path='/api/v1/auth/mfa/recovery-codes'
    assert client.post(path,json={'code':'000000','current_password':account['password']}).status_code==403
    assert client.post(path,json={'code':'000000','current_password':'wrong'},headers=account['csrf']).status_code==403
    # Advance the stored clock marker back, without waiting for a real TOTP window.
    with account['owner']() as db:
        user=db.get(User,account['user'].id);user.mfa_last_timestep-=2;db.commit()
    response=client.post(path,json={'code':pyotp.TOTP(setup['secret']).now(),'current_password':account['password']},headers=account['csrf'])
    assert response.status_code==200,response.text
    assert len(response.json()['recovery_codes'])==10
    assert set(response.json()['recovery_codes']).isdisjoint(codes)
    assert client.post('/api/v1/auth/login',json={'email':account['user'].email,'password':account['password'],'recovery_code':codes[0]}).status_code==401
    assert client.post('/api/v1/auth/mfa/confirm',json={'code':pyotp.TOTP(setup['secret']).now()},headers=account['csrf']).status_code==409


def test_recovery_code_consumed_once_concurrently(account):
    from fastapi.testclient import TestClient
    from app.main import app
    _,codes=enroll(account);barrier=Barrier(2)
    def login():
        client=TestClient(app)
        try:
            barrier.wait(timeout=10)
            return client.post('/api/v1/auth/login',json={'email':account['user'].email,'password':account['password'],'recovery_code':codes[0]}).status_code
        finally:client.close()
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:login(),range(2)))
    assert sorted(results)==[200,401]


def test_recovery_code_does_not_enable_cross_account_login(account):
    from app.models import User
    from app.security import hash_password
    _,codes=enroll(account)
    with account['owner']() as db:
        user=User(email='other-'+account['user'].email,full_name='Other',password_hash=hash_password(account['password']),is_super_admin=True,mfa_enabled_at=datetime.now(timezone.utc));db.add(user);db.commit()
    response=account['client'].post('/api/v1/auth/login',json={'email':user.email,'password':account['password'],'recovery_code':codes[0]})
    assert response.status_code==401


def test_disabling_mfa_clears_recovery_codes(account):
    from app.models import User
    setup,_=enroll(account)
    with account['owner']() as db:
        user=db.get(User,account['user'].id);user.mfa_last_timestep-=2;db.commit()
    response=account['client'].post('/api/v1/auth/mfa/disable',json={'code':pyotp.TOTP(setup['secret']).now(),'current_password':account['password']},headers=account['csrf'])
    assert response.status_code==200,response.text
    with account['owner']() as db:assert db.get(User,account['user'].id).mfa_recovery_hashes==[]
