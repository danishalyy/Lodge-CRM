from uuid import uuid4
from sqlalchemy import select


def test_lodge_preferences_update_and_me_are_scoped_and_audited(account):
    from app.models import AuditLog
    client=account['client'];path=f"/api/v1/lodges/{account['lodge'].id}/preferences"
    assert client.get(path).json()['currency']=='ZAR'
    body={'currency':'USD','date_format':'dd/MM/yyyy'}
    assert client.patch(path,json=body).status_code==403
    response=client.patch(path,json=body,headers=account['csrf'])
    assert response.status_code==200,response.text
    assert response.json()['date_format']=='dd/MM/yyyy'
    membership=client.get('/api/v1/auth/me').json()['memberships'][0]
    assert membership['currency']=='USD' and membership['date_format']=='dd/MM/yyyy'
    with account['owner']() as db:
        row=db.scalar(select(AuditLog).where(AuditLog.lodge_id==account['lodge'].id,AuditLog.action=='lodge.preferences_updated'))
        assert row and row.actor_user_id==account['user'].id


def test_preferences_reject_invalid_values_and_other_lodges(account):
    from app.models import Lodge
    client=account['client'];path=f"/api/v1/lodges/{account['lodge'].id}/preferences"
    for body in [{'currency':'XYZ','date_format':'locale'},{'currency':'USD','date_format':'invalid'}]:
        assert client.patch(path,json=body,headers=account['csrf']).status_code==422
    with account['owner']() as db:
        other=Lodge(name='Other format '+uuid4().hex);db.add(other);db.commit()
    otherpath=f'/api/v1/lodges/{other.id}/preferences'
    assert client.get(otherpath).status_code==403
    assert client.patch(otherpath,json={'currency':'USD','date_format':'locale'},headers=account['csrf']).status_code==403


def test_read_only_can_read_but_not_change_preferences(account):
    from app.models import Membership,Role
    with account['owner']() as db:
        membership=db.scalar(select(Membership).where(Membership.user_id==account['user'].id));membership.role_id=db.scalar(select(Role.id).where(Role.key=='read_only'));db.commit()
    path=f"/api/v1/lodges/{account['lodge'].id}/preferences"
    assert account['client'].get(path).status_code==200
    assert account['client'].patch(path,json={'currency':'USD','date_format':'locale'},headers=account['csrf']).status_code==403


def test_registration_rejects_invalid_timezone_with_field_error(account):
    from datetime import date,datetime,timedelta,timezone
    from app.models import User
    with account['owner']() as db:
        user=db.get(User,account['user'].id);user.is_super_admin=True;user.mfa_enabled_at=datetime.now(timezone.utc);db.commit()
    response=account['client'].post('/api/v1/platform/lodges',json={'name':'Time zone test','package':'Basic','timezone':'Not/AZone','start_date':date.today().isoformat(),'expiry_date':(date.today()+timedelta(days=365)).isoformat(),'admin_name':'Owner Name','admin_email':'owner@example.com'},headers=account['csrf'])
    assert response.status_code==422,response.text
    assert response.json()['detail'][0]['loc']==['body','timezone']
