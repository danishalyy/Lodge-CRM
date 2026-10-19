"""role scoping, entitlement engine, password reset and MFA foundation"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='0005_access_hardening'
down_revision='0004_operations_intelligence'
branch_labels=None
depends_on=None

FEATURES={
    'Basic': {
        'dashboard','guests','stays','staff','tasks','guest_requests','housekeeping','maintenance','units',
        'activities','fleet','notifications','reports','audit','guest_mobile','staff_mobile','branding.basic'
    },
    'Standard': {
        'dashboard','guests','stays','staff','tasks','guest_requests','housekeeping','maintenance','units',
        'activities','fleet','notifications','reports','audit','guest_mobile','staff_mobile','branding.basic',
        'departments','transfers','fb','ranger','vehicle_checklists','fuel','wildlife','offline_mobile','ai',
        'ai_knowledge','document_knowledge','advanced_reports','branding.enhanced','pms.optional'
    },
    'Premium': {
        'dashboard','guests','stays','staff','tasks','guest_requests','housekeeping','maintenance','units',
        'activities','fleet','notifications','reports','audit','guest_mobile','staff_mobile','branding.basic',
        'departments','transfers','fb','ranger','vehicle_checklists','fuel','wildlife','offline_mobile','ai',
        'ai_knowledge','document_knowledge','advanced_reports','branding.enhanced','pms.optional',
        'live_gps','trip_history','geofencing','telemetry','device_health','advanced_fuel_alerts','satellite_tracking',
        'advanced_ai','ai_daily_summary','ai_weekly_report','ai_insights','advanced_wildlife_analytics',
        'workflow_automation','pms_integrations','accounting_integrations','messaging_integrations','api_access','branding.advanced'
    }
}

def upgrade():
    op.add_column('users', sa.Column('mfa_secret_encrypted', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('mfa_enabled_at', sa.DateTime(timezone=True), nullable=True))

    op.add_column('memberships', sa.Column('department_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_membership_department','memberships','departments',['department_id'],['id'],ondelete='SET NULL')
    op.create_index('ix_memberships_department_id','memberships',['department_id'])
    op.execute("""UPDATE memberships m SET department_id=s.department_id FROM staff_profiles s
                WHERE s.user_id=m.user_id AND s.lodge_id=m.lodge_id AND m.department_id IS NULL""")

    for table in ['maintenance_tickets','activities','transfers']:
        op.add_column(table, sa.Column('department_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(f'fk_{table}_department',table,'departments',['department_id'],['id'],ondelete='SET NULL')
        op.create_index(f'ix_{table}_department_id',table,['department_id'])
    op.execute("""UPDATE maintenance_tickets m SET department_id=s.department_id FROM staff_profiles s WHERE s.id=m.assigned_staff_id AND m.department_id IS NULL""")
    op.execute("""UPDATE activities a SET department_id=s.department_id FROM staff_profiles s WHERE s.id=a.guide_staff_id AND a.department_id IS NULL""")
    op.execute("""UPDATE transfers t SET department_id=s.department_id FROM staff_profiles s WHERE s.id=t.driver_staff_id AND t.department_id IS NULL""")

    op.create_table('plans',
        sa.Column('key',sa.String(30),primary_key=True),sa.Column('name',sa.String(80),nullable=False),sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.create_table('plan_entitlements',
        sa.Column('plan_key',sa.String(30),sa.ForeignKey('plans.key',ondelete='CASCADE'),primary_key=True),
        sa.Column('feature_key',sa.String(120),primary_key=True),sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.create_table('lodge_entitlement_overrides',
        sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('feature_key',sa.String(120),primary_key=True),sa.Column('enabled',sa.Boolean(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_lodge_entitlement_overrides_lodge_id','lodge_entitlement_overrides',['lodge_id'])
    op.execute("ALTER TABLE lodge_entitlement_overrides ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lodge_entitlement_overrides FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY lodge_entitlement_overrides_tenant_policy ON lodge_entitlement_overrides
        USING (current_setting('app.is_super_admin', true)='true' OR lodge_id::text=current_setting('app.current_lodge_id', true))
        WITH CHECK (current_setting('app.is_super_admin', true)='true' OR lodge_id::text=current_setting('app.current_lodge_id', true))""")
    for plan in ['Basic','Standard','Premium']:
        op.execute(sa.text("INSERT INTO plans(key,name,is_active) VALUES(:k,:n,true)").bindparams(k=plan,n=plan))
        for feature in sorted(FEATURES[plan]):
            op.execute(sa.text("INSERT INTO plan_entitlements(plan_key,feature_key,enabled) VALUES(:p,:f,true)").bindparams(p=plan,f=feature))

    op.create_table('password_reset_tokens',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column('user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('token_hash',sa.String(64),nullable=False,unique=True),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('used_at',sa.DateTime(timezone=True)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_password_reset_tokens_user_id','password_reset_tokens',['user_id'])
    op.create_index('ix_password_reset_tokens_token_hash','password_reset_tokens',['token_hash'],unique=True)
    op.create_index('ix_password_reset_tokens_expires_at','password_reset_tokens',['expires_at'])

    permissions={
        'units.status.manage':'Update operational room status without changing room configuration',
        'tasks.own.manage':'Accept, start and complete tasks assigned to the current staff member',
        'requests.own.manage':'Work on guest requests assigned to the current staff member',
        'activities.own.manage':'Update activities assigned to the current guide',
        'transfers.own.manage':'Update transfers assigned to the current driver',
        'maintenance.report':'Report a maintenance issue without maintenance administration access',
        'dashboard.view':'View the lodge command centre',
        'guests.dietary.view':'View guest dietary/allergy information relevant to service delivery',
    }
    for k,d in permissions.items():
        op.execute(sa.text("INSERT INTO permissions(id,key,description) VALUES(gen_random_uuid(),:k,:d) ON CONFLICT(key) DO NOTHING").bindparams(k=k,d=d))

    # Remove over-broad legacy grants before applying the scoped matrix.
    for role,perm in [
        ('housekeeping','units.manage'),('housekeeping','maintenance.manage'),('housekeeping','guests.view'),('housekeeping','stays.view'),
        ('ranger','activities.manage'),('ranger','guests.view'),('ranger','stays.view'),
        ('driver','transfers.manage'),('driver','guests.view'),('driver','stays.view'),
        ('fb','guests.view'),('fb','stays.view'),
        ('department_manager','guests.view'),('department_manager','stays.view'),('department_manager','vehicles.view'),('department_manager','fuel.view'),('department_manager','wildlife.view'),('department_manager','ranger.view'),
        ('department_manager','memory.view'),('ranger','memory.view'),('maintenance','memory.view'),('finance','memory.view')
    ]:
        op.execute(sa.text("""DELETE FROM role_permissions rp USING roles r, permissions p
            WHERE rp.role_id=r.id AND rp.permission_id=p.id AND r.key=:r AND p.key=:p""").bindparams(r=role,p=perm))
    grants={
        'housekeeping':['units.status.manage','tasks.own.manage','requests.own.manage','maintenance.report'],
        'ranger':['tasks.own.manage','activities.own.manage','maintenance.report'],
        'driver':['tasks.own.manage','transfers.own.manage','maintenance.report','maintenance.view'],
        'general_staff':['tasks.own.manage','requests.own.manage','maintenance.report','maintenance.view'],
        'maintenance':['tasks.own.manage'],
        'department_manager':['transfers.manage','dashboard.view'],
        'lodge_admin':['dashboard.view','guests.dietary.view'],
        'front_office':['guests.dietary.view'],
        'fb':['tasks.own.manage','requests.own.manage','guests.dietary.view'],
        'read_only':['dashboard.view'],
    }
    for role,perms in grants.items():
        for perm in perms:
            op.execute(sa.text("""INSERT INTO role_permissions(role_id,permission_id)
                SELECT r.id,p.id FROM roles r,permissions p WHERE r.key=:r AND p.key=:p ON CONFLICT DO NOTHING""").bindparams(r=role,p=perm))

def downgrade():
    # Restore legacy broad grants removed above.
    for role,perm in [('housekeeping','units.manage'),('housekeeping','maintenance.manage'),('housekeeping','guests.view'),('housekeeping','stays.view'),('ranger','activities.manage'),('ranger','guests.view'),('ranger','stays.view'),('driver','transfers.manage'),('driver','guests.view'),('driver','stays.view'),('fb','guests.view'),('fb','stays.view'),('department_manager','guests.view'),('department_manager','stays.view'),('department_manager','vehicles.view'),('department_manager','fuel.view'),('department_manager','wildlife.view'),('department_manager','ranger.view'),('department_manager','memory.view'),('ranger','memory.view'),('maintenance','memory.view'),('finance','memory.view')]:
        op.execute(sa.text("""INSERT INTO role_permissions(role_id,permission_id)
            SELECT r.id,p.id FROM roles r,permissions p WHERE r.key=:r AND p.key=:p ON CONFLICT DO NOTHING""").bindparams(r=role,p=perm))
    for perm in ['units.status.manage','tasks.own.manage','requests.own.manage','activities.own.manage','transfers.own.manage','maintenance.report','dashboard.view','guests.dietary.view']:
        op.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key=:p)").bindparams(p=perm))
        op.execute(sa.text("DELETE FROM permissions WHERE key=:p").bindparams(p=perm))
    op.drop_table('password_reset_tokens')
    op.execute('DROP POLICY IF EXISTS lodge_entitlement_overrides_tenant_policy ON lodge_entitlement_overrides')
    op.drop_table('lodge_entitlement_overrides')
    op.drop_table('plan_entitlements')
    op.drop_table('plans')
    for table in ['transfers','activities','maintenance_tickets']:
        op.drop_index(f'ix_{table}_department_id',table_name=table)
        op.drop_constraint(f'fk_{table}_department',table_name=table,type_='foreignkey')
        op.drop_column(table,'department_id')
    op.drop_index('ix_memberships_department_id',table_name='memberships')
    op.drop_constraint('fk_membership_department',table_name='memberships',type_='foreignkey')
    op.drop_column('memberships','department_id')
    op.drop_column('users','mfa_enabled_at')
    op.drop_column('users','mfa_secret_encrypted')
