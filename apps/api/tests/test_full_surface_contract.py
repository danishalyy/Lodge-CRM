from pathlib import Path
import ast, re, sys
import pytest

API_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(API_ROOT))
ROOT=API_ROOT
MAIN_PATH=ROOT/'app'/'main.py'
MAIN=MAIN_PATH.read_text()
SEC=(ROOT/'app'/'security.py').read_text()
MODELS=(ROOT/'app'/'models.py').read_text()
SCHEMAS=(ROOT/'app'/'schemas.py').read_text()
MIG_DIR=ROOT/'alembic'/'versions'
WEB=ROOT.parent/'web'

def routes():
    tree=ast.parse(MAIN)
    out=[]
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            for d in n.decorator_list:
                if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and isinstance(d.func.value,ast.Name) and d.func.value.id=='app' and d.func.attr in {'get','post','patch','put','delete'}:
                    path=ast.literal_eval(d.args[0])
                    out.append((d.func.attr.upper(),path,n.name,ast.get_source_segment(MAIN,d) or '',ast.get_source_segment(MAIN,n) or ''))
    return out

ROUTES=routes()

def test_api_surface_is_large_and_unique():
    assert len(ROUTES) >= 110
    keys=[(m,p) for m,p,*_ in ROUTES]
    assert len(keys)==len(set(keys))

@pytest.mark.parametrize('method,path,name,deco,body',[r for r in ROUTES if r[0] in {'POST','PATCH','PUT','DELETE'} and r[1] not in {'/api/v1/auth/login','/api/v1/auth/activate','/api/v1/auth/password-reset/request','/api/v1/auth/password-reset/confirm'}])
def test_every_authenticated_mutation_has_csrf(method,path,name,deco,body):
    assert 'require_csrf' in deco, f'{method} {path} lacks CSRF guard'

@pytest.mark.parametrize('method,path,name,deco,body',[r for r in ROUTES if r[1].startswith('/api/v1/lodges/{lodge_id}')])
def test_every_lodge_route_has_tenant_auth(method,path,name,deco,body):
    assert ('Depends(require_permission' in body or 'Depends(require_lodge_access' in body), f'{method} {path} lacks lodge authorization dependency'

@pytest.mark.parametrize('method,path,name,deco,body',[r for r in ROUTES if r[1].startswith('/api/v1/lodges/{lodge_id}') and r[0] in {'POST','PATCH','PUT','DELETE'}])
def test_every_lodge_mutation_has_subscription_write_gate(method,path,name,deco,body):
    assert ('write=True' in body or 'ensure_subscription_write_allowed' in body), f'{method} {path} does not enforce subscription write state'

@pytest.mark.parametrize('method,path,name,deco,body',[r for r in ROUTES if r[1].startswith('/api/v1/platform/')])
def test_every_platform_route_requires_super_admin(method,path,name,deco,body):
    assert 'Depends(require_super_admin)' in body, f'{method} {path} is not Super Admin guarded'


def test_auth_security_contract():
    for token in ['Argon2','httponly=True','samesite="lax"','token_hash','revoked_at','expires_at']:
        assert token.lower() in (SEC+MAIN).lower()
    assert 'X-Lodge-Id' not in MAIN and 'X-Platform-Role' not in MAIN


def test_password_reset_revokes_existing_sessions():
    assert 'AuthSession.user_id==user.id' in MAIN
    assert 'sess.revoked_at=now' in MAIN


def test_mfa_is_real_totp_and_encrypted_at_rest():
    assert 'pyotp.TOTP' in MAIN
    assert 'encrypt_mfa_secret' in MAIN and 'decrypt_mfa_secret' in MAIN
    assert 'Fernet' in SEC


def test_subscription_states_are_complete():
    for state in ['Suspended','Pending','Expired','Expiring Soon','Active']:
        assert state in SEC or state in MAIN
    assert 'access is read-only' in SEC


def test_notification_writes_obey_expiry_read_only_rule():
    blocks=[]
    for method,path,name,_,body in ROUTES:
        if method in {'POST','PATCH'} and path in {'/api/v1/lodges/{lodge_id}/notifications/{notification_id}/read','/api/v1/lodges/{lodge_id}/notification-preferences'}:
            blocks.append(body)
    assert len(blocks)==2
    assert all('write=True' in b for b in blocks)


def test_role_catalog_exact_no_group_admin():
    txt=(MIG_DIR/'0001_production_foundation.py').read_text()
    expected=['lodge_admin','department_manager','front_office','ranger','housekeeping','maintenance','driver','fb','finance','general_staff','read_only']
    for role in expected: assert f"'{role}'" in txt
    assert 'group_admin' not in txt.lower()


def test_department_manager_scope_contracts_cover_major_modules():
    for marker in [
        'Task.department_id==ctx.department_id',
        'MaintenanceTicket.department_id==ctx.department_id',
        'Transfer.department_id==ctx.department_id',
        'GuestFeedback.department_id==ctx.department_id',
        'StaffProfile.department_id==ctx.department_id',
    ]: assert marker in MAIN


def test_own_work_scopes_cover_field_roles():
    for marker in [
        'Task.assigned_staff_id==staff.id',
        'Transfer.driver_staff_id==_require_own_staff(ctx).id',
        'Activity.guide_staff_id==_require_own_staff(ctx).id',
        'HousekeepingJob.assigned_staff_id==_require_own_staff(ctx).id',
    ]: assert marker in MAIN


def test_cross_tenant_fk_validation_is_reused():
    assert MAIN.count('ensure_fk(') >= 25
    assert 'tenant_get(' in MAIN


def test_rls_forced_in_every_tenant_migration():
    migration_text='\n'.join(p.read_text() for p in sorted(MIG_DIR.glob('*.py')))
    assert migration_text.count('FORCE ROW LEVEL SECURITY') >= 5
    assert "app.current_lodge_id" in migration_text


def test_application_db_role_cannot_bypass_rls():
    boot=(ROOT/'app'/'bootstrap_db_role.py').read_text()
    assert 'NOSUPERUSER' in boot and 'NOBYPASSRLS' in boot


def test_no_runtime_schema_create_all():
    app_py='\n'.join(p.read_text(errors='ignore') for p in (ROOT/'app').rglob('*.py'))
    assert 'metadata.create_all' not in app_py


def test_no_fake_demo_operational_seed_strings():
    text='\n'.join(p.read_text(errors='ignore') for p in MIG_DIR.glob('*.py')).lower()
    for bad in ['john doe','demo guest','sample guest','fake lodge','sample lodge']:
        assert bad not in text


def test_core_state_machine_guards_exist():
    markers=['TASK_TRANSITIONS','STAY_TRANSITIONS','REQUEST_TRANSITIONS','MAINT_TRANSITIONS','HK_TRANSITIONS','Invalid shift transition','Invalid meal service transition']
    for m in markers: assert m in MAIN


def test_booking_and_resource_conflict_guards_exist():
    for marker in ['overlapping stay','overlapping shift','overlapping activity','overlapping transfer']:
        assert marker.lower() in MAIN.lower()


def test_task_completion_requires_required_checklist():
    assert 'Complete all required checklist items' in MAIN


def test_guest_feedback_resolution_requires_resolution():
    assert 'Resolution is required before resolving feedback' in MAIN


def test_upload_security_constraints_exist():
    assert 'hashlib.sha256()' in MAIN
    assert 'checksum does not match' in MAIN.lower()
    assert 'presigned' in MAIN.lower()
    assert 'size_bytes' in SCHEMAS


def test_worker_and_beat_are_real_components():
    compose=(ROOT.parent.parent/'infra'/'docker-compose.yml').read_text()
    assert 'worker:' in compose and 'beat:' in compose and 'redis:' in compose


def test_web_routes_exist_for_every_visible_module():
    modules=(WEB/'lib'/'modules.ts').read_text()
    keys=re.findall(r"\['([^']+)','",modules)
    exempt={'settings'}
    for key in keys:
        page=WEB/'app'/'(app)'/key/'page.tsx'
        assert page.exists(), f'Module {key} has no page'


def test_web_api_has_csrf_header_support_and_credentials():
    api=(WEB/'lib'/'api.ts').read_text()
    assert "X-CSRF-Token" in api and "credentials:'include'" in api


def test_ui_has_glass_design_tokens_and_reduced_motion():
    css=(WEB/'app'/'design-system.css').read_text().lower()
    assert '--bg-base: #191c18' in css
    assert '--surface-glass:' in css and 'backdrop-filter:' in css
    assert '@supports not' in css and 'data-theme="light"' in css
    assert 'prefers-reduced-motion' in css
    assert 'transition' in css


def test_dashboard_has_calendar_and_charts_components():
    dash=(WEB/'components'/'DashboardPage.tsx').read_text()
    viz=(WEB/'components'/'DataViz.tsx').read_text()
    assert 'Calendar' in dash or 'calendar' in dash
    assert 'Chart' in dash or 'chart' in dash or 'Bar' in viz


def test_migration_revision_ids_unique_and_short_linear_chain():
    rows=[]
    for p in sorted(MIG_DIR.glob('*.py')):
        t=ast.parse(p.read_text())
        vals={}
        for n in t.body:
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in {'revision','down_revision'}:
                vals[n.targets[0].id]=ast.literal_eval(n.value)
        rows.append((p.name,vals.get('revision'),vals.get('down_revision')))
    revs=[r for _,r,_ in rows]
    assert all(r and len(r)<=32 for r in revs)
    assert len(revs)==len(set(revs))
    prev=None
    for _,rev,down in rows:
        assert down==prev
        prev=rev
