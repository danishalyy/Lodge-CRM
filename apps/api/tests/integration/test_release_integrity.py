"""Release regressions for the independently reproduced CIA/workflow defects."""
from datetime import date, timedelta
import pytest
from uuid import UUID, uuid4
from sqlalchemy import select
from app.models import User, Role, Membership, StaffProfile
from app.security import hash_password

def post(a, path, body):
 r=a['client'].post(f"/api/v1/lodges/{a['lodge'].id}"+path,json=body,headers=a['csrf'])
 assert r.status_code==200,r.text
 return r.json()

def patch(a,path,body):
 r=a['client'].patch(f"/api/v1/lodges/{a['lodge'].id}"+path,json=body,headers=a['csrf'])
 assert r.status_code==200,r.text
 return r.json()

def test_departing_stay_remains_occupied_until_checkout(account):
 a=account;c=a['client'];base=f"/api/v1/lodges/{a['lodge'].id}"
 guest=post(a,'/guests',{'first_name':'Departure','last_name':'Probe'})
 room=post(a,'/rooms',{'name':'Departure probe'})
 stay=post(a,'/stays',{'guest_id':guest['id'],'unit_id':room['id'],'arrival_date':date.today().isoformat(),'departure_date':(date.today()+timedelta(days=1)).isoformat()})
 for status in ['arriving','in_house','departing']:patch(a,'/stays/'+stay['id'],{'status':status})
 post(a,'/housekeeping-jobs',{'unit_id':room['id'],'job_type':'inspection'})
 rows=c.get(base+'/rooms').json();row=next(x for x in rows if x['id']==room['id'])
 assert row['status']=='occupied',row
 assert row['current_guest']=='Departure Probe'
 result=c.patch(base+'/rooms/'+room['id'],json={'status':'ready'},headers=a['csrf'])
 assert result.status_code==409,result.text

def test_anonymization_masks_immutable_legacy_history(account):
 a=account;guest=post(a,'/guests',{'first_name':'PrivacyOriginal','last_name':'Person'})
 from app.models import OperationalEvent
 with a['owner']() as db:
  legacy=OperationalEvent(lodge_id=a['lodge'].id,actor_user_id=a['user'].id,event_type='guest.created',resource_type='guest',resource_id=guest['id'],summary='Guest PrivacyOriginal Person added to CRM',detail='PrivacyOriginal Person')
  db.add(legacy);db.commit();legacy_id=legacy.id
 post(a,'/guests/'+guest['id']+'/anonymize',{})
 r=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/operational-memory")
 assert r.status_code==200,r.text
 assert 'PrivacyOriginal' not in r.text
 dashboard=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/dashboard")
 assert dashboard.status_code==200,dashboard.text
 assert 'PrivacyOriginal' not in dashboard.text
 with a['owner']() as db:
  assert db.get(OperationalEvent,legacy_id).summary=='Guest PrivacyOriginal Person added to CRM'

def test_vehicle_release_waits_for_all_critical_tickets(account):
 a=account;v=post(a,'/vehicles',{'registration':uuid4().hex[:10],'name':'Review vehicle'})
 one=post(a,'/maintenance',{'title':'Critical brakes','priority':'critical','vehicle_id':v['id']})
 two=post(a,'/maintenance',{'title':'Critical steering','priority':'critical','vehicle_id':v['id']})
 patch(a,'/maintenance/'+one['id'],{'status':'in_progress'})
 patch(a,'/maintenance/'+one['id'],{'status':'completed','resolution':'Brakes fixed'})
 r=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/vehicles")
 assert r.status_code==200,r.text
 row=next(x for x in r.json() if x['id']==v['id']); assert row['status']=='maintenance',row
 r=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/maintenance")
 assert next(x for x in r.json() if x['id']==two['id'])['status']=='open'

def test_custom_department_history_keeps_resource_scope(account):
 a=account;c=a['client'];base=f"/api/v1/lodges/{a['lodge'].id}"
 da=post(a,'/departments',{'name':'Department A'})
 db=post(a,'/departments',{'name':'Department B'})
 post(a,'/tasks',{'title':'Department B confidential work','department_id':db['id']})
 post(a,'/tasks',{'title':'Department A permitted work','department_id':da['id']})
 custom=post(a,'/custom-roles',{'name':'Department history reader','base_role_key':'department_manager','permission_keys':['memory.view','tasks.view']})
 password='Review-only long password 123!'
 with a['owner']() as session:
  u=User(email=uuid4().hex+'@example.com',full_name='Department A manager',password_hash=hash_password(password));session.add(u);session.flush()
  role=session.scalar(select(Role).where(Role.key=='department_manager'))
  m=Membership(user_id=u.id,lodge_id=a['lodge'].id,role_id=role.id,custom_role_id=UUID(custom['id']),department_id=UUID(da['id']))
  staff=StaffProfile(lodge_id=a['lodge'].id,user_id=u.id,full_name=u.full_name,department_id=UUID(da['id']))
  session.add_all([m,staff]);session.commit();email=u.email
 c.cookies.clear()
 r=c.post('/api/v1/auth/login',json={'email':email,'password':password});assert r.status_code==200,r.text
 r=c.get(base+'/operational-memory');assert r.status_code==200,r.text
 assert not any('Department B confidential work' in x['summary'] for x in r.json())
 assert any('Department A permitted work' in x['summary'] for x in r.json())

def test_disabled_guest_feature_blocks_reads_and_writes(account):
 from app.models import LodgeEntitlementOverride
 a=account
 with a['owner']() as db:
  db.add(LodgeEntitlementOverride(lodge_id=a['lodge'].id,feature_key='guests',enabled=False,reason='Review verifies disabled feature enforcement'))
  db.commit()
 base=f"/api/v1/lodges/{a['lodge'].id}"
 access=a['client'].get(base+'/feature-access?feature_key=guests'); assert access.status_code==200 and not access.json()['available'],access.text
 denied=a['client'].get(base+'/guests'); assert denied.status_code==403,denied.text
 created=a['client'].post(base+'/guests',json={'first_name':'Disabled','last_name':'Feature'},headers=a['csrf'])
 assert created.status_code==403,created.text

def test_disaster_recovery_revokes_sessions_without_erasing_audit(account):
 from app.ops.post_restore import invalidate_restored_access
 from app.models import AuditLog
 from sqlalchemy import func
 a=account
 post(a,'/guests',{'first_name':'Recovery','last_name':'Probe'})
 with a['owner']() as db:
  before=db.scalar(select(func.count()).select_from(AuditLog))
  invalidate_restored_access(db)
  assert db.scalar(select(func.count()).select_from(AuditLog))==before
 response=a['client'].get('/api/v1/auth/me')
 assert response.status_code==401,response.text

def test_readiness_cannot_bypass_an_unresolved_vehicle_fault(account):
 a=account;vehicle=post(a,'/vehicles',{'registration':uuid4().hex[:10]})
 post(a,'/maintenance',{'title':'Unsafe brakes','priority':'critical','vehicle_id':vehicle['id']})
 r=a['client'].patch(f"/api/v1/lodges/{a['lodge'].id}/vehicles/{vehicle['id']}",json={'status':'ready'},headers=a['csrf'])
 assert r.status_code==409,r.text


def test_raising_maintenance_priority_blocks_the_vehicle(account):
 a=account;vehicle=post(a,'/vehicles',{'registration':uuid4().hex[:10]})
 ticket=post(a,'/maintenance',{'title':'Investigate brakes','vehicle_id':vehicle['id']})
 patch(a,'/maintenance/'+ticket['id'],{'priority':'critical'})
 rows=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/vehicles").json()
 assert next(row for row in rows if row['id']==vehicle['id'])['status']=='maintenance'


def test_future_critical_service_does_not_block_vehicle_early(account):
 from datetime import datetime,timezone
 a=account;vehicle=post(a,'/vehicles',{'registration':uuid4().hex[:10]})
 post(a,'/maintenance',{'title':'Future brake service','priority':'critical','vehicle_id':vehicle['id'],'scheduled_for':(datetime.now(timezone.utc)+timedelta(days=30)).isoformat()})
 rows=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/vehicles").json()
 assert next(row for row in rows if row['id']==vehicle['id'])['status']=='ready'


def test_dirty_room_cannot_check_in_until_prepared(account):
 a=account;room=post(a,'/rooms',{'name':'Readiness room'})
 guest=post(a,'/guests',{'first_name':'Readiness','last_name':'Guest'})
 stay=post(a,'/stays',{'unit_id':room['id'],'guest_id':guest['id'],'arrival_date':date.today().isoformat(),'departure_date':(date.today()+timedelta(days=1)).isoformat()})
 patch(a,'/stays/'+stay['id'],{'status':'arriving'})
 patch(a,'/rooms/'+room['id'],{'status':'cleaning'})
 r=a['client'].patch(f"/api/v1/lodges/{a['lodge'].id}/stays/{stay['id']}",json={'status':'in_house'},headers=a['csrf'])
 assert r.status_code==409,r.text
 patch(a,'/rooms/'+room['id'],{'status':'ready'})
 assert patch(a,'/stays/'+stay['id'],{'status':'in_house'})['status']=='in_house'


def test_checkout_retains_blocking_room_maintenance(account):
 a=account;room=post(a,'/rooms',{'name':'Fault during stay'})
 guest=post(a,'/guests',{'first_name':'Checkout','last_name':'Guest'})
 stay=post(a,'/stays',{'unit_id':room['id'],'guest_id':guest['id'],'arrival_date':date.today().isoformat(),'departure_date':(date.today()+timedelta(days=1)).isoformat()})
 for status in ['arriving','in_house']:patch(a,'/stays/'+stay['id'],{'status':status})
 post(a,'/maintenance',{'title':'Critical room fault','unit_id':room['id'],'priority':'critical'})
 for status in ['departing','completed']:patch(a,'/stays/'+stay['id'],{'status':status})
 rows=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/rooms").json()
 assert next(row for row in rows if row['id']==room['id'])['status']=='maintenance'
 r=a['client'].patch(f"/api/v1/lodges/{a['lodge'].id}/rooms/{room['id']}",json={'status':'ready'},headers=a['csrf'])
 assert r.status_code==409,r.text


@pytest.mark.parametrize('feature,endpoint', [
 ('guests','guests'),('stays','stays'),('units','rooms'),('staff','staff'),
 ('fleet','vehicles'),('fuel','fuel'),('tasks','tasks'),('activities','activities'),
 ('maintenance','maintenance'),('housekeeping','housekeeping-jobs'),
 ('guest_requests','requests'),('reports','reports/summary'),
])
def test_disabled_core_module_does_not_expose_records(account,feature,endpoint):
 from app.models import LodgeEntitlementOverride
 with account['owner']() as db:
  db.add(LodgeEntitlementOverride(lodge_id=account['lodge'].id,feature_key=feature,enabled=False,reason='Explicit operator restriction'))
  db.commit()
 response=account['client'].get(f"/api/v1/lodges/{account['lodge'].id}/"+endpoint)
 assert response.status_code==403,response.text


def test_redis_outage_keeps_login_attempts_limited(account, monkeypatch):
    import redis
    from fastapi import HTTPException
    from types import SimpleNamespace
    from app import main
    from app.services.login_limits import LocalLoginLimits

    def unavailable(*args, **kwargs):
        raise redis.ConnectionError('unavailable')

    monkeypatch.setattr(main.redis_client, 'incr', unavailable)
    monkeypatch.setattr(main.redis_client, 'delete', unavailable)
    monkeypatch.setattr(main, 'fallback_login_limits', LocalLoginLimits())
    request = SimpleNamespace(client=SimpleNamespace(host='192.0.2.1'))
    for _ in range(main.settings.login_rate_limit):
        main.rate_limit_login(request, 'owner@example.com')
    with pytest.raises(HTTPException) as denied:
        main.rate_limit_login(request, 'OWNER@example.com')
    assert denied.value.status_code == 429
    main.clear_login_limit(request, 'OWNER@example.com')
    main.rate_limit_login(request, 'owner@example.com')


def test_request_and_worker_redis_connections_have_bounded_timeouts(account):
    from app import main, worker
    for client in [main.redis_client, worker.redis_client]:
        connection = client.connection_pool.connection_kwargs
        assert 0 < connection['socket_timeout'] <= 2
        assert 0 < connection['socket_connect_timeout'] <= 2


def test_dashboard_does_not_bypass_disabled_modules(account):
    from datetime import datetime, timezone
    from app.models import LodgeEntitlementOverride
    a=account
    post(a,'/tasks',{'title':'Disabled private task','due_at':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()})
    with a['owner']() as db:
        db.add(LodgeEntitlementOverride(lodge_id=a['lodge'].id,feature_key='tasks',enabled=False,reason='No task module'))
        db.commit()
    r=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/dashboard")
    assert r.status_code==200,r.text
    assert r.json()['metrics']['open_tasks'] is None
    assert r.json()['metrics']['overdue_tasks'] is None
    assert 'Disabled private task' not in r.text


def test_dashboard_only_custom_role_cannot_read_other_modules(account):
    from datetime import datetime, timezone
    a=account
    post(a,'/tasks',{'title':'Not authorised for overview','due_at':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()})
    custom=post(a,'/custom-roles',{'name':'Overview only','base_role_key':'front_office','permission_keys':['dashboard.view']})
    with a['owner']() as db:
        member=db.scalar(select(Membership).where(Membership.user_id==a['user'].id,Membership.lodge_id==a['lodge'].id))
        member.role_id=db.scalar(select(Role.id).where(Role.key=='front_office'))
        member.custom_role_id=UUID(custom['id'])
        db.commit()
    r=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/dashboard")
    assert r.status_code==200,r.text
    assert all(value is None for value in r.json()['metrics'].values())
    assert not r.json()['attention'] and not r.json()['events']
    assert 'Not authorised for overview' not in r.text


def scheduled_drive(a, kind):
    from datetime import datetime, timezone
    from app.models import LodgeEntitlementOverride
    with a['owner']() as db:
        db.add(LodgeEntitlementOverride(lodge_id=a['lodge'].id,feature_key='vehicle_checklists',enabled=False,reason='Checklist-independent state regression'))
        db.commit()
    staff=post(a,'/staff',{'full_name':'Drive operator'})
    vehicle=post(a,'/vehicles',{'registration':uuid4().hex[:10]})
    start=datetime.now(timezone.utc)+timedelta(hours=1)
    if kind=='activities':
        body={'activity_type':'game_drive','title':'State safety drive','starts_at':start.isoformat(),'ends_at':(start+timedelta(hours=1)).isoformat(),'guide_staff_id':staff['id'],'vehicle_id':vehicle['id']}
    else:
        guest=post(a,'/guests',{'first_name':'Transfer','last_name':'Safety'})
        body={'transfer_type':'pickup','guest_id':guest['id'],'driver_staff_id':staff['id'],'vehicle_id':vehicle['id'],'scheduled_at':start.isoformat(),'expected_end_at':(start+timedelta(hours=1)).isoformat(),'pickup_location':'Airport','dropoff_location':'Lodge'}
    drive=post(a,'/'+kind,body)
    path='/'+kind+'/'+drive['id']
    patch(a,path,{'status':'confirmed'})
    return vehicle,path


def due_fault(a,vehicle):
    from datetime import datetime,timezone
    from app.models import MaintenanceTicket
    ticket=post(a,'/maintenance',{'title':'Scheduled critical fault','priority':'critical','vehicle_id':vehicle['id'],'scheduled_for':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
    # Advance the existing schedule to due without rewriting cached vehicle state.
    with a['owner']() as db:
        db.get(MaintenanceTicket,UUID(ticket['id'])).scheduled_for=datetime.now(timezone.utc)-timedelta(minutes=1)
        db.commit()
    return ticket


@pytest.mark.parametrize('kind,start_state',[('activities','in_progress'),('transfers','en_route')])
def test_due_scheduled_fault_blocks_departure_even_if_cached_vehicle_state_is_ready(account,kind,start_state):
    a=account;vehicle,path=scheduled_drive(a,kind)
    due_fault(a,vehicle)
    r=a['client'].patch(f"/api/v1/lodges/{a['lodge'].id}"+path,json={'status':start_state},headers=a['csrf'])
    assert r.status_code==409,r.text


@pytest.mark.parametrize('kind,start_state',[('activities','in_progress'),('transfers','en_route')])
def test_return_does_not_release_vehicle_with_newly_due_fault(account,kind,start_state):
    a=account;vehicle,path=scheduled_drive(a,kind)
    patch(a,path,{'status':start_state})
    due_fault(a,vehicle)
    if kind=='transfers':patch(a,path,{'status':'arrived'})
    patch(a,path,{'status':'completed'})
    rows=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/vehicles").json()
    assert next(row for row in rows if row['id']==vehicle['id'])['status']=='maintenance'


@pytest.mark.parametrize('kind,start_state',[('activities','in_progress'),('transfers','en_route')])
def test_fault_release_preserves_active_drive_and_manual_ready_cannot_override_it(account,kind,start_state):
    a=account;vehicle,path=scheduled_drive(a,kind)
    patch(a,path,{'status':start_state})
    ticket=post(a,'/maintenance',{'title':'Drive fault','priority':'critical','vehicle_id':vehicle['id']})
    patch(a,'/maintenance/'+ticket['id'],{'status':'in_progress'})
    patch(a,'/maintenance/'+ticket['id'],{'status':'completed','resolution':'Repair verified'})
    rows=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/vehicles").json()
    assert next(row for row in rows if row['id']==vehicle['id'])['status']=='on_drive'
    r=a['client'].patch(f"/api/v1/lodges/{a['lodge'].id}/vehicles/{vehicle['id']}",json={'status':'ready'},headers=a['csrf'])
    assert r.status_code==409,r.text
    if kind=='transfers':patch(a,path,{'status':'arrived'})
    patch(a,path,{'status':'completed'})
    rows=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/vehicles").json()
    assert next(row for row in rows if row['id']==vehicle['id'])['status']=='ready'


@pytest.mark.parametrize('kind,start_state',[('activities','in_progress'),('transfers','en_route')])
def test_departed_journey_cannot_reassign_vehicle_and_leave_old_vehicle_in_use(account,kind,start_state):
    a=account;vehicle,path=scheduled_drive(a,kind)
    patch(a,path,{'status':start_state})
    replacement=post(a,'/vehicles',{'registration':uuid4().hex[:10]})
    r=a['client'].patch(f"/api/v1/lodges/{a['lodge'].id}"+path,json={'vehicle_id':replacement['id']},headers=a['csrf'])
    assert r.status_code==409,r.text
    rows=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/vehicles").json()
    assert next(row for row in rows if row['id']==vehicle['id'])['status']=='on_drive'
    assert next(row for row in rows if row['id']==replacement['id'])['status']=='ready'


def test_housekeeping_workflow_updates_authoritative_unit_state(account):
    # Replace the old source-string check, which accidentally matched a vehicle
    # assignment, with a real database-backed housekeeping lifecycle.
    a=account;room=post(a,'/rooms',{'name':'Inspected readiness'})
    job=post(a,'/housekeeping-jobs',{'unit_id':room['id'],'job_type':'cleaning'})
    for status,expected in [('in_progress','cleaning'),('awaiting_inspection','awaiting_inspection'),('completed','ready')]:
        patch(a,'/housekeeping-jobs/'+job['id'],{'status':status})
        rows=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/rooms").json()
        assert next(row for row in rows if row['id']==room['id'])['status']==expected


@pytest.mark.parametrize('event_type,resource,feature',[
    ('fuel.recorded','vehicle','fuel'),
    ('guest.feedback_created','guest','guest_feedback'),
    ('housekeeping.created','unit','housekeeping'),
])
def test_history_parent_record_alias_does_not_bypass_child_module_entitlement(account,event_type,resource,feature):
    from app.models import OperationalEvent,LodgeEntitlementOverride
    a=account
    paths={'guest':('/guests',{'first_name':'Alias','last_name':'Guest'}),'vehicle':('/vehicles',{'registration':uuid4().hex[:10]}),'unit':('/rooms',{'name':'Alias room'})}
    path,body=paths[resource];record=post(a,path,body)
    with a['owner']() as db:
        db.add(OperationalEvent(lodge_id=a['lodge'].id,actor_user_id=a['user'].id,event_type=event_type,resource_type=resource,resource_id=record['id'],summary='Disabled child capability confidential details'))
        db.add(LodgeEntitlementOverride(lodge_id=a['lodge'].id,feature_key=feature,enabled=False,reason='Child capability unavailable'))
        db.commit()
    for endpoint in ['operational-memory','dashboard']:
        r=a['client'].get(f"/api/v1/lodges/{a['lodge'].id}/"+endpoint)
        assert r.status_code==200,r.text
        assert 'Disabled child capability confidential details' not in r.text
