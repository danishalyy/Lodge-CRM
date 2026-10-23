from uuid import uuid4


def test_rand_default_and_restored_cost_tracking(account):
    from app.models import Vehicle
    client=account['client'];base=f"/api/v1/lodges/{account['lodge'].id}"
    assert client.get(base+'/preferences').json()['currency']=='ZAR'
    with account['owner']() as db:
        vehicle=Vehicle(lodge_id=account['lodge'].id,registration=uuid4().hex,name='Restored cost test');db.add(vehicle);db.commit()
    fuel=client.post(base+'/fuel',json={'vehicle_id':str(vehicle.id),'litres':10,'odometer_km':100,'cost_cents':25000},headers=account['csrf'])
    assert fuel.status_code==200,fuel.text
    assert next(row for row in client.get(base+'/fuel').json() if row['id']==fuel.json()['id'])['cost_cents']==25000
    ticket=client.post(base+'/maintenance',json={'title':'Restored workshop test'},headers=account['csrf'])
    assert ticket.status_code==200,ticket.text
    ticket_id=ticket.json()['id']
    part=client.post(base+f'/maintenance/{ticket_id}/parts',json={'part_name':'Filter','quantity':2,'unit_cost_cents':12500},headers=account['csrf'])
    assert part.status_code==200,part.text
    assert part.json()['ticket_cost_cents']==25000
    assert client.get(base+f'/maintenance/{ticket_id}/parts').json()[0]['total_cost_cents']==25000
    reports=client.get(base+'/reports/summary').json()
    assert reports['maintenance']['cost_cents']==25000 and reports['fleet']['fuel_cost_cents']==25000
    assert client.patch(base+'/preferences',json={'date_format':'dd/MM/yyyy','currency':'USD'},headers=account['csrf']).status_code==200
    assert client.get('/api/v1/auth/me').json()['memberships'][0]['currency']=='USD'
