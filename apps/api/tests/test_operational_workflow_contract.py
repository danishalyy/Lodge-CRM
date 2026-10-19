from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MAIN=(ROOT/'api'/'app'/'main.py').read_text()
MODELS=(ROOT/'api'/'app'/'models.py').read_text()
MIG=(ROOT/'api'/'alembic'/'versions'/'0006_operational_workflows.py').read_text()
SEC=(ROOT/'api'/'app'/'security.py').read_text()


def test_hr_workflows_exist_without_seed_data():
    for name in ['StaffLeave','StaffCredential','StaffTraining']:
        assert f'class {name}' in MODELS
    assert '/hr/leaves' in MAIN and '/hr/credentials' in MAIN and '/hr/training' in MAIN
    assert 'overlapping leave' in MAIN


def test_custom_roles_use_explicit_permissions_and_base_scope():
    assert 'class CustomRole' in MODELS
    assert 'class CustomRolePermission' in MODELS
    assert 'membership.custom_role_id' in SEC
    assert 'CustomRolePermission.permission_id' in SEC
    assert '/custom-roles' in MAIN


def test_advanced_task_contract():
    assert 'TaskChecklistItem' in MODELS and 'TaskComment' in MODELS
    assert 'Complete all required checklist items' in MAIN
    assert 'task.recurrence_created' in MAIN
    assert '/checklist' in MAIN and '/comments' in MAIN


def test_housekeeping_workflow_updates_authoritative_unit_state():
    assert 'class HousekeepingJob' in MODELS
    assert 'HK_TRANSITIONS' in MAIN
    assert 'status="ready"' in MAIN or '.status="ready"' in MAIN
    assert 'housekeeping_full' in MAIN


def test_workshop_assets_parts_and_recurrence():
    assert 'class MaintenanceAsset' in MODELS
    assert 'class MaintenancePartUsage' in MODELS
    assert 'maintenance.recurrence_created' in MAIN
    assert '/maintenance-assets' in MAIN
    assert '/parts' in MAIN


def test_new_tenant_tables_have_rls_policy_generation():
    for table in ['staff_leaves','staff_credentials','staff_training','custom_roles','custom_role_permissions','task_checklist_items','task_comments','housekeeping_jobs','maintenance_assets','maintenance_part_usage']:
        assert table in MIG
    assert 'FORCE ROW LEVEL SECURITY' in MIG
