from uuid import uuid4
from sqlalchemy import select


def test_catalog_copy_update_assign_and_deactivate(account):
    from app.models import User,StaffProfile,Membership,Role,AuditLog
    from app.security import hash_password
    c=account['client'];base=f"/api/v1/lodges/{account['lodge'].id}"
    catalog=c.get(base+'/role-catalog').json()
    assert len(catalog['presets'])==11
    preset=next(p for p in catalog['presets'] if p['key']=='general_staff')
    assert set(preset['copy_permission_keys'])==set(preset['permission_keys'])
    result=c.post(base+'/custom-roles',json={'name':'Copied tasks','base_role_key':preset['copy_base_role_key'],'permission_keys':preset['copy_permission_keys']},headers=account['csrf'])
    assert result.status_code==200,result.text
    role_id=result.json()['id']
    with account['owner']() as db:
        user=User(email=uuid4().hex+'@example.com',full_name='Worker',password_hash=hash_password('Worker long password!'));db.add(user);db.flush()
        role=db.scalar(select(Role).where(Role.key=='front_office'));member=Membership(user_id=user.id,lodge_id=account['lodge'].id,role_id=role.id);staff=StaffProfile(lodge_id=account['lodge'].id,user_id=user.id,full_name='Worker');db.add_all([member,staff]);db.commit();original=role.id
    assert c.patch(base+f'/staff/{staff.id}/custom-role',json={'custom_role_id':role_id},headers=account['csrf']).status_code==200
    assert next(r for r in c.get(base+'/custom-roles').json() if r['id']==role_id)['staff_count']==1
    assert c.patch(base+'/custom-roles/'+role_id,json={'name':'Updated name','permission_keys':['tasks.view']},headers=account['csrf']).status_code==200
    assert c.patch(base+'/custom-roles/'+role_id,json={'is_active':False},headers=account['csrf']).status_code==200
    with account['owner']() as db:
        m=db.get(Membership,member.id);assert m.custom_role_id is None and m.role_id==original
        assert len(db.scalars(select(AuditLog).where(AuditLog.resource_id==role_id)).all())>=3


def test_no_sensitive_or_unowned_grants_and_cross_lodge(account):
    from app.models import Permission,RolePermission,Membership,Lodge
    c=account['client'];base=f"/api/v1/lodges/{account['lodge'].id}"
    for key in ['staff.manage','roles.custom.manage','departments.manage','notifications.delivery.view']:
        r=c.post(base+'/custom-roles',json={'name':'Denied','base_role_key':'general_staff','permission_keys':[key]},headers=account['csrf']);assert r.status_code==422,r.text
    with account['owner']() as db:
        from app.models import Role
        membership=db.scalar(select(Membership).where(Membership.user_id==account['user'].id))
        limited=Role(key='limited_'+uuid4().hex,name='Limited role administrator');db.add(limited);db.flush()
        for permission in db.scalars(select(Permission).where(Permission.key.in_(['roles.custom.manage','staff.manage','staff.view','tasks.view']))):db.add(RolePermission(role_id=limited.id,permission_id=permission.id))
        membership.role_id=limited.id
        other=Lodge(name='Other role '+uuid4().hex);db.add(other);db.commit()
    assert c.post(base+'/custom-roles',json={'name':'Denied grant','base_role_key':'front_office','permission_keys':['guests.manage']},headers=account['csrf']).status_code==403
    assert c.get(f'/api/v1/lodges/{other.id}/role-catalog').status_code==403
    assert c.get(f'/api/v1/lodges/{other.id}/custom-roles').status_code==403


def test_staff_creation_can_assign_custom_role_atomically(account):
    c=account['client'];base=f"/api/v1/lodges/{account['lodge'].id}"
    r=c.post(base+'/custom-roles',json={'name':'Task viewer','base_role_key':'general_staff','permission_keys':['tasks.view']},headers=account['csrf']);assert r.status_code==200,r.text
    role_id=r.json()['id']
    response=c.post(base+'/staff',json={'full_name':'Custom Worker','email':uuid4().hex+'@example.com','invite_role_key':'general_staff','custom_role_id':role_id},headers=account['csrf']);assert response.status_code==200,response.text
    from app.models import Membership
    with account['owner']() as db:
        member=db.scalar(select(Membership).where(Membership.user_id==response.json()['user_id']));assert str(member.custom_role_id)==role_id
