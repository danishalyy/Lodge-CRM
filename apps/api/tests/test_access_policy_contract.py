from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[2]
MIG=(ROOT/'api'/'alembic'/'versions'/'0005_access_subscription_hardening.py').read_text()
MAIN=(ROOT/'api'/'app'/'main.py').read_text()
SEC=(ROOT/'api'/'app'/'security.py').read_text()


def _features():
    tree=ast.parse(MIG)
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FEATURES' for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError('FEATURES not found')


def test_package_hierarchy_and_key_features():
    f=_features()
    assert f['Basic'] <= f['Standard'] <= f['Premium']
    assert {'guests','stays','tasks','housekeeping','maintenance','fleet'} <= f['Basic']
    assert {'departments','transfers','ranger','fuel','wildlife','offline_mobile','ai'} <= f['Standard']
    assert {'live_gps','telemetry','advanced_ai','api_access','workflow_automation'} <= f['Premium']


def test_no_group_admin_role_reintroduced():
    foundation=(ROOT/'api'/'alembic'/'versions'/'0001_production_foundation.py').read_text()
    assert "'group_admin'" not in foundation


def test_subscription_hard_lock_and_expired_read_only_contract():
    assert 'state == "Suspended"' in SEC
    assert 'state == "Pending"' in SEC
    assert 'state == "Expired"' in SEC
    assert 'access is read-only' in SEC


def test_department_and_own_record_scopes_are_enforced_in_routes():
    assert 'Task.department_id==ctx.department_id' in MAIN
    assert 'MaintenanceTicket.department_id==ctx.department_id' in MAIN
    assert 'Transfer.department_id==ctx.department_id' in MAIN
    assert 'Task.assigned_staff_id==staff.id' in MAIN
    assert 'Transfer.driver_staff_id==_require_own_staff(ctx).id' in MAIN
    assert 'Activity.guide_staff_id==_require_own_staff(ctx).id' in MAIN


def test_dashboard_requires_permission_and_department_scope():
    assert 'require_permission("dashboard.view")' in MAIN
    assert '"type":"department"' in MAIN


def test_fake_header_auth_is_not_used():
    assert 'X-Lodge-Id' not in MAIN
    assert 'X-Platform-Role' not in MAIN
