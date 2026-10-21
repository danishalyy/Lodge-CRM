"""Real database invitation, private inbox and durable SMTP delivery regressions."""
import re
import smtplib
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.config import settings
from app.models import AccountEmail, Invitation, User, Membership, NotificationRecipient, NotificationDelivery
from app.email_service import decrypt_payload

@pytest.fixture
def mail(monkeypatch):
    monkeypatch.setattr(settings,'smtp_host','smtp.gmail.com')
    monkeypatch.setattr(settings,'smtp_from_email','sender@gmail.com')
    monkeypatch.setattr(settings,'smtp_username','sender@gmail.com')
    monkeypatch.setattr(settings,'smtp_password','test-only-app-password')
    monkeypatch.setattr(settings,'smtp_use_tls',True)
    monkeypatch.setattr(settings,'smtp_use_ssl',False)


def invite(account, email=None):
    path=f"/api/v1/lodges/{account['lodge'].id}/staff"
    response=account['client'].post(path,json={'full_name':'Invited Owner','email':email or f'{uuid4().hex}@example.com','invite_role_key':'general_staff'},headers=account['csrf'])
    assert response.status_code==200,response.text
    with account['owner']() as db:
        row=db.scalar(select(AccountEmail).where(AccountEmail.invitation_id==response.json()['invitation_id']))
        payload=decrypt_payload(row.encrypted_payload)
        token=re.search(r'/activate#token=([^\s]+)',payload['body']).group(1)
        return response.json(),row,token


@pytest.mark.parametrize('domain',['gmail.com','business.example'])
def test_invitation_is_encrypted_owner_sets_password(account,mail,domain):
    data,row,token=invite(account,f'{uuid4().hex}@{domain}')
    assert data['activation_token'] is None
    assert data['activation_email_queued'] and not data['activation_email_sent']
    assert token not in row.encrypted_payload and token not in str(data)
    with account['owner']() as db:
        target=db.get(User,row.user_id)
        assert not target.is_active and not target.email_verified_at
    client=account['client']
    preview=client.post('/api/v1/auth/invitations/preview',json={'token':token})
    assert preview.status_code==200 and preview.json()['workspace']==account['lodge'].name
    client.cookies.clear()
    result=client.post('/api/v1/auth/activate',json={'token':token,'password':'A private owner passphrase 42!'})
    assert result.status_code==200,result.text
    assert client.get('/api/v1/auth/me').json()['id']==str(row.user_id)
    assert client.post('/api/v1/auth/activate',json={'token':token,'password':'Different passphrase 234!'}).status_code==400
    assert client.get('/api/v1/platform/users').status_code==403
    with account['owner']() as db:
        assert db.get(User,row.user_id).email_verified_at


def test_resend_invalidates_link_without_changing_role(account,mail):
    data,row,token=invite(account)
    path=f"/api/v1/lodges/{account['lodge'].id}/staff/{data['id']}/invitation/resend"
    assert account['client'].post(path,headers=account['csrf']).status_code==429
    with account['owner']() as db:
        inv=db.get(Invitation,row.invitation_id);inv.created_at-=timedelta(minutes=2)
        role=db.scalar(select(Membership.role_id).where(Membership.user_id==row.user_id));db.commit()
    response=account['client'].post(path,headers=account['csrf'])
    assert response.status_code==200,response.text
    assert account['client'].post('/api/v1/auth/invitations/preview',json={'token':token}).status_code==400
    with account['owner']() as db:
        old=db.get(AccountEmail,row.id)
        assert old.status=='cancelled' and old.encrypted_payload is None
        assert db.scalar(select(Membership.role_id).where(Membership.user_id==row.user_id))==role


def test_expired_invitation_cannot_activate_or_send(account,mail,monkeypatch):
    data,row,token=invite(account)
    with account['owner']() as db:
        db.get(Invitation,row.invitation_id).expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    from app import email_jobs
    sent=[];monkeypatch.setattr(email_jobs,'send_email',lambda *args:sent.append(args))
    email_jobs.process_account_emails(account['application'])
    assert not sent
    with account['owner']() as db:
        assert db.get(AccountEmail,row.id).status=='cancelled'
    assert account['client'].post('/api/v1/auth/activate',json={'token':token,'password':'Owner password long enough!'}).status_code==400


def test_smtp_retry_lease_recovery_and_payload_erasure(account,mail,monkeypatch):
    _,row,_=invite(account)
    from app import email_jobs
    def fail(*args): raise smtplib.SMTPAuthenticationError(535,b'secret token or password must never persist')
    monkeypatch.setattr(email_jobs,'send_email',fail)
    email_jobs.process_account_emails(account['application'])
    with account['owner']() as db:
        queued=db.get(AccountEmail,row.id)
        assert queued.status=='failed' and queued.attempts==1
        assert 'secret token' not in queued.last_error
        queued.status='sending';queued.lease_expires_at=datetime.now(timezone.utc)-timedelta(minutes=1);db.commit()
    sent=[];monkeypatch.setattr(email_jobs,'send_email',lambda *args:sent.append(args))
    email_jobs.process_account_emails(account['application'])
    assert len(sent)==1
    with account['owner']() as db:
        delivered=db.get(AccountEmail,row.id)
        assert delivered.status=='sent' and delivered.encrypted_payload is None and delivered.attempts==2
    email_jobs.process_account_emails(account['application'])
    assert len(sent)==1


def test_inbox_is_private_and_preferences_control_email(account,mail):
    from app.notification_service import create_notification
    from app.security import hash_password
    with account['owner']() as db:
        user=db.get(User,account['user'].id);user.email_verified_at=datetime.now(timezone.utc)
        other=User(email=f'{uuid4().hex}@example.com',full_name='Other account',password_hash=hash_password('Other private passphrase!'))
        db.add(other);db.flush()
        db.add(Membership(user_id=other.id,lodge_id=account['lodge'].id,role_id=db.scalar(select(Membership.role_id).where(Membership.user_id==user.id))))
        db.flush()
        own=create_notification(db,lodge_id=account['lodge'].id,notification_type='test.private',severity='high',title='Private owner update',recipient_user_ids=[user.id])
        foreign=create_notification(db,lodge_id=account['lodge'].id,notification_type='test.private',severity='high',title='Other owner update',recipient_user_ids=[other.id]);db.commit()
    client=account['client'];base='/api/v1/auth/notifications'
    notices=client.get(base).json()
    assert any(n['id']==str(own.id) for n in notices)
    assert all(n['id']!=str(foreign.id) for n in notices)
    assert client.post(f'{base}/{foreign.id}/read',headers=account['csrf']).status_code==404
    assert client.get(base+'/summary').json()['unread']==1
    assert client.post(f'{base}/{own.id}/read',headers=account['csrf']).status_code==200
    assert client.get(base+'/summary').json()['unread']==0
    assert client.patch('/api/v1/auth/notification-preferences',json={'email_enabled':False,'email_min_severity':'critical'},headers=account['csrf']).status_code==200
    with account['owner']() as db:
        new=create_notification(db,lodge_id=account['lodge'].id,notification_type='test.private',severity='critical',title='In app only',recipient_user_ids=[account['user'].id]);db.commit()
        assert not db.scalar(select(NotificationDelivery).where(NotificationDelivery.notification_id==new.id))
    assert client.post(f'{base}/{own.id}/archive',headers=account['csrf']).status_code==200
    assert all(n['id']!=str(own.id) for n in client.get(base).json())


def test_account_email_outbox_forces_tenant_rls(account,mail):
    _,row,_=invite(account)
    from app.db import set_rls_context
    with account['application']() as db:
        set_rls_context(db,str(uuid4()),False)
        assert db.get(AccountEmail,row.id) is None
    assert account['client'].get('/api/v1/platform/email').status_code==403
    assert account['client'].post('/api/v1/platform/users/invite',json={'email':'admin@example.com','full_name':'Denied Admin'},headers=account['csrf']).status_code==403


def test_platform_admin_invitation_requires_mfa_and_owner_activation(account,mail):
    from app.models import AuthSession
    with account['owner']() as db:
        actor=db.get(User,account['user'].id);actor.is_super_admin=True;db.commit()
    path='/api/v1/platform/users/invite'
    body={'full_name':'New Platform Owner','email':f'{uuid4().hex}@gmail.com'}
    assert account['client'].post(path,json=body,headers=account['csrf']).status_code==403
    with account['owner']() as db:
        actor=db.get(User,account['user'].id);actor.mfa_enabled_at=datetime.now(timezone.utc)
        session=db.scalar(select(AuthSession).where(AuthSession.user_id==actor.id));session.mfa_verified_at=datetime.now(timezone.utc);db.commit()
    result=account['client'].post(path,json=body,headers=account['csrf'])
    assert result.status_code==200,result.text
    with account['owner']() as db:
        row=db.scalar(select(AccountEmail).where(AccountEmail.invitation_id==result.json()['invitation_id']))
        token=re.search(r'/activate#token=([^\s]+)',decrypt_payload(row.encrypted_payload)['body']).group(1)
        assert db.get(Invitation,row.invitation_id).lodge_id is None
    account['client'].cookies.clear()
    response=account['client'].post('/api/v1/auth/activate',json={'token':token,'password':'Private platform passphrase 42!'})
    assert response.status_code==200,response.text
    me=account['client'].get('/api/v1/auth/me').json()
    assert me['is_super_admin'] and not me['mfa_enabled']
    assert account['client'].get('/api/v1/platform/users').status_code==403


def test_membership_revocation_cancels_pending_notification_email(account,mail,monkeypatch):
    from app.notification_service import create_notification
    from app import email_jobs
    with account['owner']() as db:
        user=db.get(User,account['user'].id);user.email_verified_at=datetime.now(timezone.utc)
        n=create_notification(db,lodge_id=account['lodge'].id,notification_type='test.revoke',severity='critical',title='Private alert',recipient_user_ids=[user.id]);db.commit()
        member=db.scalar(select(Membership).where(Membership.user_id==user.id));member.is_active=False;db.commit()
    sent=[];monkeypatch.setattr(email_jobs,'send_email',lambda *args:sent.append(args))
    email_jobs.process_notification_emails(account['application'])
    assert not sent
    with account['owner']() as db:
        row=db.scalar(select(NotificationDelivery).where(NotificationDelivery.notification_id==n.id))
        assert row.status=='cancelled'


def test_notification_delivery_retries_then_records_acceptance(account,mail,monkeypatch):
    from app.notification_service import create_notification
    from app import email_jobs
    with account['owner']() as db:
        user=db.get(User,account['user'].id);user.email_verified_at=datetime.now(timezone.utc)
        notice=create_notification(db,lodge_id=account['lodge'].id,notification_type='test.retry',severity='high',title='Owner update',recipient_user_ids=[user.id]);db.commit()
    def fail(*args,**kwargs):raise OSError('private SMTP details')
    monkeypatch.setattr(email_jobs,'send_email',fail)
    email_jobs.process_notification_emails(account['application'])
    with account['owner']() as db:
        row=db.scalar(select(NotificationDelivery).where(NotificationDelivery.notification_id==notice.id))
        assert row.status=='failed' and 'private SMTP' not in row.last_error
        row.status='sending';row.lease_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1);db.commit()
    sent=[];monkeypatch.setattr(email_jobs,'send_email',lambda *args,**kwargs:sent.append(args))
    email_jobs.process_notification_emails(account['application'])
    assert len(sent)==1
    with account['owner']() as db:
        row=db.scalar(select(NotificationDelivery).where(NotificationDelivery.notification_id==notice.id))
        assert row.status=='sent' and row.sent_at and row.attempts==2 and not row.last_error


def test_existing_staff_email_cannot_claim_another_lodge_account(account,mail):
    from app.security import hash_password
    with account['owner']() as db:
        other=User(email=f'{uuid4().hex}@example.com',full_name='Private other lodge owner',password_hash=hash_password('Other owner long passphrase!'))
        db.add(other);db.commit()
    path=f"/api/v1/lodges/{account['lodge'].id}/staff"
    result=account['client'].post(path,json={'full_name':'Rejected Claim','email':other.email,'invite_role_key':'finance'},headers=account['csrf'])
    assert result.status_code==409
    from app.models import StaffProfile
    with account['owner']() as db:
        assert not db.scalar(select(StaffProfile).where(StaffProfile.lodge_id==account['lodge'].id,StaffProfile.email==other.email)), 'failed invite must roll back the staff profile too'


def test_password_recovery_queues_encrypted_link_anonymously_and_revokes_sessions(account,mail):
    from app.models import AuthSession
    client=account['client'];client.cookies.clear()
    response=client.post('/api/v1/auth/password-reset/request',json={'email':account['user'].email})
    assert response.status_code==200,response.text
    with account['owner']() as db:
        row=db.scalar(select(AccountEmail).where(AccountEmail.user_id==account['user'].id,AccountEmail.kind=='password_reset'))
        assert row and row.status=='pending'
        token=re.search(r'/reset-password#token=([^\s]+)',decrypt_payload(row.encrypted_payload)['body']).group(1)
        assert token not in response.text and token not in row.encrypted_payload
    result=client.post('/api/v1/auth/password-reset/confirm',json={'token':token,'password':'New private recovery passphrase 42!'})
    assert result.status_code==200,result.text
    assert client.post('/api/v1/auth/password-reset/confirm',json={'token':token,'password':'Cannot replay this password 42!'}).status_code==400
    with account['owner']() as db:
        assert db.get(User,account['user'].id).email_verified_at
        assert all(s.revoked_at for s in db.scalars(select(AuthSession).where(AuthSession.user_id==account['user'].id)))
