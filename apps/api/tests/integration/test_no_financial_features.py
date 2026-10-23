from uuid import uuid4
from sqlalchemy import select


def test_financial_fields_rejected_and_history_untouched(account):
    from app.models import Lodge,Vehicle,FuelRecord,MaintenanceTicket,MaintenancePartUsage
    c=account['client'];base=f"/api/v1/lodges/{account['lodge'].id}"
    with account['owner']() as db:
        lodge=db.get(Lodge,account['lodge'].id);lodge.currency='ZAR'
        vehicle=Vehicle(lodge_id=lodge.id,registration=uuid4().hex,name='Test vehicle');db.add(vehicle);db.flush()
        ticket=MaintenanceTicket(lodge_id=lodge.id,title='Historical service',cost_cents=12500,created_by_user_id=account['user'].id)
        fuel=FuelRecord(lodge_id=lodge.id,vehicle_id=vehicle.id,litres=10,odometer_km=100,cost_cents=4500,created_by_user_id=account['user'].id)
        db.add_all([ticket,fuel]);db.flush()
        part=MaintenancePartUsage(lodge_id=lodge.id,maintenance_ticket_id=ticket.id,part_name='Old part',quantity=2,unit_cost_cents=500);db.add(part);db.commit()
    assert c.patch(base+'/preferences',json={'date_format':'locale','currency':'USD'},headers=account['csrf']).status_code==422
    assert c.patch(base+'/preferences',json={'date_format':'dd/MM/yyyy'},headers=account['csrf']).status_code==200
    for path in ['/preferences','/fuel','/maintenance',f'/maintenance/{ticket.id}/parts','/reports/summary']:
        r=c.get(base+path);assert r.status_code==200,r.text
        assert 'currency' not in r.text and 'cost_cents' not in r.text
    assert c.post(base+'/fuel',json={'vehicle_id':str(vehicle.id),'litres':10,'odometer_km':110,'cost_cents':100},headers=account['csrf']).status_code==422
    assert c.patch(base+f'/maintenance/{ticket.id}',json={'cost_cents':100},headers=account['csrf']).status_code==422
    assert c.post(base+f'/maintenance/{ticket.id}/parts',json={'part_name':'New part','quantity':2,'unit_cost_cents':100},headers=account['csrf']).status_code==422
    result=c.post(base+f'/maintenance/{ticket.id}/parts',json={'part_name':'New part','quantity':2},headers=account['csrf']);assert result.status_code==200,result.text
    assert 'cost' not in result.text
    csv=c.get(base+'/reports/summary.csv');assert csv.status_code==200 and 'cost_cents' not in csv.text
    with account['owner']() as db:
        assert db.get(Lodge,account['lodge'].id).currency=='ZAR'
        assert db.get(MaintenanceTicket,ticket.id).cost_cents==12500
        assert db.get(FuelRecord,fuel.id).cost_cents==4500
        assert db.get(MaintenancePartUsage,part.id).unit_cost_cents==500
        from datetime import datetime,timezone
        from app.models import User,AuthSession
        user=db.get(User,account['user'].id);user.is_super_admin=True;user.mfa_enabled_at=datetime.now(timezone.utc)
        session=db.scalar(select(AuthSession).where(AuthSession.user_id==user.id));session.mfa_verified_at=datetime.now(timezone.utc);db.commit()
    plans=c.get('/api/v1/platform/plans');assert plans.status_code==200
    for plan in plans.json():
        assert 'accounting_integrations' not in plan['features']+plan['planned_features']
        assert 'accounting_integrations' not in [f['key'] for f in plan['feature_catalog']]
