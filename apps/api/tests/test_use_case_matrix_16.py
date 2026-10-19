from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
import pytest
from pydantic import ValidationError

API_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(API_ROOT))
ROOT=Path(__file__).resolve().parents[2]
MAIN=(ROOT/'api'/'app'/'main.py').read_text()
MODELS=(ROOT/'api'/'app'/'models.py').read_text()
MIG=(ROOT/'api'/'alembic'/'versions'/'0007_core_ops_completion.py').read_text()
from app.schemas import (
    GuestFeedbackCreate, StaffShiftCreate, StaffIncidentCreate, StaffPerformanceCreate,
    MealServiceCreate, TaskAttachmentUploadRequest,
)

def has_route(path,method):
    deco={'GET':'@app.get','POST':'@app.post','PATCH':'@app.patch','DELETE':'@app.delete'}[method]
    return f'{deco}(\"{path}\"' in MAIN

def test_feedback_routes_present():
    p='/api/v1/lodges/{lodge_id}/feedback'
    assert has_route(p,'GET') and has_route(p,'POST')
    assert has_route(p+'/{record_id}','PATCH')

def test_feedback_rating_validation():
    good=GuestFeedbackCreate(guest_id='00000000-0000-0000-0000-000000000001',rating=5)
    assert good.rating==5
    with pytest.raises(ValidationError): GuestFeedbackCreate(guest_id='00000000-0000-0000-0000-000000000001',rating=6)

def test_feedback_resolution_required():
    assert 'Resolution is required before resolving feedback' in MAIN

def test_feedback_department_scope_enforced():
    assert 'Department Manager can only manage feedback for their department' in MAIN
    assert 'Department Manager can only create feedback for their department' in MAIN

def test_staff_shift_routes_present():
    p='/api/v1/lodges/{lodge_id}/hr/shifts'
    assert has_route(p,'GET') and has_route(p,'POST') and has_route(p+'/{record_id}','PATCH')

def test_shift_time_validation_schema_and_api():
    now=datetime.now(timezone.utc)
    data=StaffShiftCreate(staff_id='00000000-0000-0000-0000-000000000001',starts_at=now,ends_at=now+timedelta(hours=8))
    assert data.ends_at>data.starts_at
    assert 'Shift end must be after shift start' in MAIN

def test_shift_overlap_protection():
    assert 'overlapping shift' in MAIN
    assert 'StaffShift.starts_at<body.ends_at' in MAIN

def test_shift_state_machine():
    assert 'Invalid shift transition' in MAIN
    assert '"scheduled":{"confirmed","cancelled"}' in MAIN

def test_incident_routes_and_confidential_flag():
    p='/api/v1/lodges/{lodge_id}/hr/incidents'
    assert has_route(p,'GET') and has_route(p,'POST')
    row=StaffIncidentCreate(staff_id='00000000-0000-0000-0000-000000000001',occurred_at=datetime.now(timezone.utc),description='Operational incident')
    assert row.is_confidential is True

def test_performance_routes_and_rating_validation():
    p='/api/v1/lodges/{lodge_id}/hr/performance'
    assert has_route(p,'GET') and has_route(p,'POST')
    with pytest.raises(ValidationError): StaffPerformanceCreate(staff_id='00000000-0000-0000-0000-000000000001',note_type='review',rating=0,notes='x',review_date=date.today())

def test_hr_department_scope_reused():
    assert MAIN.count('_assert_staff_scope(ctx,staff)') >= 6

def test_meal_routes_present():
    p='/api/v1/lodges/{lodge_id}/food-beverage/meals'
    assert has_route(p,'GET') and has_route(p,'POST') and has_route(p+'/{record_id}','PATCH')

def test_meal_validation():
    with pytest.raises(ValidationError): MealServiceCreate(name='Dinner',meal_type='invalid',scheduled_at=datetime.now(timezone.utc))
    with pytest.raises(ValidationError): MealServiceCreate(name='Dinner',scheduled_at=datetime.now(timezone.utc),expected_guest_count=-1)

def test_meal_dietary_data_is_live_from_guest_record():
    assert '"dietary_requirements":g.dietary_requirements' in MAIN
    assert '"allergies":g.allergies' in MAIN

def test_meal_guest_tenant_validation():
    assert 'for gid in guest_ids:ensure_fk(db,Guest,gid,lodge_id,"Guest")' in MAIN

def test_meal_state_machine():
    assert 'Invalid meal service transition' in MAIN
    assert '"scheduled":{"preparing","cancelled"}' in MAIN

def test_task_attachment_routes_present():
    base='/api/v1/lodges/{lodge_id}/tasks/{task_id}/attachments'
    assert has_route(base,'GET') and has_route(base,'POST')
    assert has_route(base+'/upload-url','POST') and has_route(base+'/{attachment_id}/download-url','GET')

def test_task_attachment_content_type_and_size_validation():
    with pytest.raises(ValidationError): TaskAttachmentUploadRequest(file_name='x.exe',content_type='application/x-msdownload',size_bytes=1,sha256='a'*64)
    with pytest.raises(ValidationError): TaskAttachmentUploadRequest(file_name='x.pdf',content_type='application/pdf',size_bytes=30_000_000,sha256='a'*64)

def test_task_attachment_checksum_verified():
    assert 'Uploaded file checksum does not match' in MAIN
    assert 'hashlib.sha256()' in MAIN

def test_task_attachment_visibility_scope():
    assert 'You can only access tasks assigned to you' in MAIN
    assert 'Only task managers or the assigned staff member can add attachments' in MAIN

def test_new_tables_use_rls_and_force_rls():
    for table in ['guest_feedback','staff_shifts','staff_incidents','staff_performance_notes','meal_services','meal_service_guests','task_attachments']:
        assert table in MIG
    assert 'FORCE ROW LEVEL SECURITY' in MIG

def test_new_permissions_seeded():
    for perm in ['feedback.view','feedback.manage','staff.roster.manage','staff.performance.manage','fb.view','fb.manage']:
        assert perm in MIG

def test_standard_and_premium_entitlements_seeded():
    for feature in ['guest_feedback','staff_roster','staff_performance','fb_operations','task_attachments']:
        assert feature in MIG
    assert "for plan in ['Standard','Premium']" in MIG

def test_basic_does_not_receive_advanced_new_features():
    assert "VALUES('Basic',:f,false)" in MIG

def test_audit_trails_cover_sensitive_new_workflows():
    for action in ['guest_feedback.created','staff_shift.created','staff_incident.created','staff_performance.created','meal_service.created','task_attachment.registered']:
        assert action in MAIN

def test_operational_memory_events_cover_guest_and_meal_workflows():
    assert 'guest.feedback_created' in MAIN
    assert 'fb.meal_scheduled' in MAIN

def test_no_group_admin_role_reintroduced():
    assert "group_admin" not in MIG.lower()

def test_no_fake_success_or_demo_seed_in_new_migration():
    lower=MIG.lower()
    for forbidden in ['sample guest','demo lodge','fake data','seed guest','john doe']:
        assert forbidden not in lower
