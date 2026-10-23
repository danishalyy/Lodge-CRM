from uuid import uuid4
from sqlalchemy import select


def test_lodge_preferences_update_and_me_are_scoped_and_audited(account):
    from app.models import AuditLog
    client=account['client'];path=f"/api/v1/lodges/{account['lodge'].id}/preferences"
    assert 'currency' not in client.get(path).json()
    body={'date_format':'dd/MM/yyyy'}
    assert client.patch(path,json=body).status_code==403
    response=client.patch(path,json=body,headers=account['csrf'])
    assert response.status_code==200,response.text
    assert response.json()['date_format']=='dd/MM/yyyy'
    membership=client.get('/api/v1/auth/me').json()['memberships'][0]
    assert 'currency' not in membership and membership['date_format']=='dd/MM/yyyy'
    with account['owner']() as db:
        row=db.scalar(select(AuditLog).where(AuditLog.lodge_id==account['lodge'].id,AuditLog.action=='lodge.preferences_updated'))
        assert row and row.actor_user_id==account['user'].id


def test_preferences_reject_invalid_values_and_other_lodges(account):
    from app.models import Lodge
    client=account['client'];path=f"/api/v1/lodges/{account['lodge'].id}/preferences"
    for body in [{'currency':'USD','date_format':'locale'},{'date_format':'invalid'}]:
        assert client.patch(path,json=body,headers=account['csrf']).status_code==422
    with account['owner']() as db:
        other=Lodge(name='Other format '+uuid4().hex);db.add(other);db.commit()
    otherpath=f'/api/v1/lodges/{other.id}/preferences'
    assert client.get(otherpath).status_code==403
    assert client.patch(otherpath,json={'date_format':'locale'},headers=account['csrf']).status_code==403


def test_read_only_can_read_but_not_change_preferences(account):
    from app.models import Membership,Role
    with account['owner']() as db:
        membership=db.scalar(select(Membership).where(Membership.user_id==account['user'].id));membership.role_id=db.scalar(select(Role.id).where(Role.key=='read_only'));db.commit()
    path=f"/api/v1/lodges/{account['lodge'].id}/preferences"
    assert account['client'].get(path).status_code==200
    assert account['client'].patch(path,json={'date_format':'locale'},headers=account['csrf']).status_code==403


def test_registration_rejects_invalid_timezone_with_field_error(account):
    from datetime import date,datetime,timedelta,timezone
    from app.models import User
    with account['owner']() as db:
        user=db.get(User,account['user'].id);user.is_super_admin=True;user.mfa_enabled_at=datetime.now(timezone.utc);db.commit()
    response=account['client'].post('/api/v1/platform/lodges',json={'name':'Time zone test','package':'Basic','timezone':'Not/AZone','start_date':date.today().isoformat(),'expiry_date':(date.today()+timedelta(days=365)).isoformat(),'admin_name':'Owner Name','admin_email':'owner@example.com'},headers=account['csrf'])
    assert response.status_code==422,response.text
    assert response.json()['detail'][0]['loc']==['body','timezone']


def test_new_currency_defaults_preserve_explicit_lodge_choices(account):
    from app.models import Lodge
    from sqlalchemy import text
    with account['owner']() as db:
        explicit=Lodge(name='Existing rand choice '+uuid4().hex,currency='ZAR')
        fresh=Lodge(name='New default '+uuid4().hex)
        db.add_all([explicit,fresh]);db.flush()
        # Exercise the database default independently of the ORM default.
        direct=db.execute(text("INSERT INTO lodges (id,name,location,timezone,brand_name,protected_species,status,created_at,updated_at) VALUES (:id,:name,'','UTC','','rhino','active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) RETURNING currency"),{'id':str(uuid4()),'name':'SQL default '+uuid4().hex}).scalar_one()
        db.commit();db.refresh(explicit);db.refresh(fresh)
        assert explicit.currency=='ZAR' and fresh.currency=='PKR' and direct=='PKR'
