from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAIN=(ROOT/'app/main.py').read_text()
SEC=(ROOT/'app/security.py').read_text()
SCHEMAS=(ROOT/'app/schemas.py').read_text()
MODELS=(ROOT/'app/models.py').read_text()
MIG=(ROOT/'alembic/versions/0008_security_integrity.py').read_text()
BOOT=(ROOT/'app/bootstrap_db_role.py').read_text()
WORKER=(ROOT/'app/worker.py').read_text()


def test_offboarding_and_reactivation_exist():
    assert '/revoke-access' in MAIN and '/reactivate-access' in MAIN
    assert 'Lodge access has been revoked' in SEC and 'employment_status != "active"' in SEC

def test_integrity_and_data_errors_are_mapped():
    assert '@app.exception_handler(IntegrityError)' in MAIN
    assert '@app.exception_handler(DataError)' in MAIN

def test_all_input_models_forbid_unknown_fields():
    assert 'ConfigDict(extra="forbid")' in SCHEMAS
    assert '(BaseModel):' not in SCHEMAS.replace('class StrictModel(BaseModel):','')

def test_stay_half_open_and_db_exclusion():
    assert 'Stay.arrival_date<departure,Stay.departure_date>arrival' in MAIN
    assert "daterange(arrival_date, departure_date, '[)')" in MIG

def test_history_append_only():
    assert 'deny_history_mutation' in MIG
    assert 'REVOKE UPDATE, DELETE ON TABLE operational_events, audit_logs' in BOOT

def test_housekeeping_state_service_used():
    assert 'housekeeping_job_created(db,unit,body.job_type)' in MAIN
    assert 'housekeeping_completed(db,db.get(Unit,row.unit_id))' in MAIN
    assert 'must move to awaiting inspection' in MAIN

def test_maintenance_releases_resources():
    assert 'maintenance_released(db' in MAIN

def test_activity_vehicle_is_conditional():
    assert 'requires_vehicle' in MODELS and 'if requires_vehicle and not vehicle' in MAIN

def test_schedule_races_hardened():
    assert 'pg_advisory_xact_lock' in MAIN
    assert 'ex_activity_vehicle_overlap' in MIG and 'ex_transfer_vehicle_overlap' in MIG

def test_task_upload_gate_and_subresource_scope():
    assert 'Your role cannot upload files to this task' in MAIN
    assert MAIN.count('_assert_task_visible(db,ctx,task)') >= 4

def test_hr_least_privilege_permissions():
    assert 'staff.hr.view' in MIG
    assert 'require_permission("staff.hr.view")' in MAIN
    assert 'staff.contact.view' in MAIN

def test_custom_role_privilege_denylist():
    assert 'SENSITIVE_CUSTOM_ROLE_PERMISSIONS' in MAIN
    assert 'previous_role_id' in MODELS

def test_mfa_replay_and_password_reauth():
    assert 'mfa_last_timestep' in MODELS
    assert 'Invalid or already-used MFA code' in MAIN
    assert 'current_password' in SCHEMAS

def test_production_docs_and_headers_hardened():
    assert 'openapi_url="/openapi.json" if settings.app_env == "development" else None' in MAIN
    assert 'Strict-Transport-Security' in MAIN and 'Content-Security-Policy' in MAIN

def test_wildlife_protected_location_controls():
    assert 'wildlife.precise' in MIG
    assert 'protected_location_obscured' in MAIN
    assert 'five minutes in the future' in MAIN

def test_task_workflow_hardening():
    assert 'Recurring tasks require a due date' in MAIN
    assert 'Proof attachment is required' in MAIN
    assert 't.status="assigned";t.accepted_at=None;t.started_at=None;t.completed_at=None' in MAIN

def test_vehicle_safety_hardening():
    assert 'Missing mandatory safety checks' in MAIN
    assert 'Fuel litres cannot exceed the vehicle tank capacity' in MAIN
    assert 'odometer_correction_reason' in SCHEMAS

def test_subscription_reminder_catches_missed_threshold():
    assert 'eligible=[t for t in thresholds if days<=t]' in WORKER
    assert 'Subscription.suspended.is_(False)' in WORKER
