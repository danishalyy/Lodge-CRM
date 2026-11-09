"""Workflow affordances are computed from server permissions and record ownership."""
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select


@pytest.mark.parametrize('module,own_role',[('activities','ranger'),('transfers','driver')])
@pytest.mark.parametrize('role',['lodge_admin','read_only','own'])
def test_workflow_capabilities_follow_the_role_and_assignment(account,module,own_role,role):
    from app.models import Activity,Transfer,StaffProfile,Guest,Membership,Role
    now=datetime.now(timezone.utc)
    lid=account['lodge'].id;uid=account['user'].id
    with account['owner']() as db:
        member=db.scalar(select(Membership).where(Membership.user_id==uid))
        member.role_id=db.scalar(select(Role.id).where(Role.key== (own_role if role=='own' else role)))
        own=StaffProfile(lodge_id=lid,user_id=uid,full_name='Assigned operator')
        other=StaffProfile(lodge_id=lid,full_name='Other operator')
        guest=Guest(lodge_id=lid,first_name='Workflow',last_name='Guest')
        db.add_all([own,other,guest]);db.flush()
        rows=[]
        for staff in [own,other]:
            if module=='activities':
                row=Activity(lodge_id=lid,activity_type='walk',title='Assigned walk',guide_staff_id=staff.id,starts_at=now,ends_at=now+timedelta(hours=1),requires_vehicle=False,created_by_user_id=uid)
            else:
                row=Transfer(lodge_id=lid,transfer_type='pickup',guest_id=guest.id,driver_staff_id=staff.id,scheduled_at=now,expected_end_at=now+timedelta(hours=1),pickup_location='Airport',dropoff_location='Lodge',created_by_user_id=uid)
            rows.append(row);db.add(row)
        db.commit();own_id=str(rows[0].id);other_id=str(rows[1].id)
    path=f'/api/v1/lodges/{lid}/{module}'
    result=account['client'].get(path)
    assert result.status_code==200,result.text
    by_id={r['id']:r for r in result.json()}
    assert by_id[own_id]['can_transition'] is (role!='read_only')
    if role=='own':
        assert other_id not in by_id
        # The capability hint does not replace write enforcement on direct URLs.
        assert account['client'].patch(path+'/'+other_id,json={'status':'confirmed'},headers=account['csrf']).status_code==403
        assert account['client'].patch(path+'/'+own_id,json={'status':'confirmed'},headers=account['csrf']).status_code==200
        assert account['client'].post(path,json={},headers=account['csrf']).status_code==403
    else:
        assert by_id[other_id]['can_transition'] is (role=='lodge_admin')
        if role=='read_only':assert account['client'].patch(path+'/'+own_id,json={'status':'confirmed'},headers=account['csrf']).status_code==403
