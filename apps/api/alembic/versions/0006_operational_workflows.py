"""staff HR, custom roles, advanced tasks, housekeeping and workshop workflows"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='0006_operational_workflows'
down_revision='0005_access_hardening'
branch_labels=None
depends_on=None

TENANT_TABLES=['staff_leaves','staff_credentials','staff_training','custom_roles','custom_role_permissions','task_checklist_items','task_comments','housekeeping_jobs','maintenance_assets','maintenance_part_usage']

def _rls(table):
    op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
    op.execute(f"""CREATE POLICY {table}_tenant_policy ON {table}
        USING (current_setting('app.is_super_admin', true)='true' OR lodge_id::text=current_setting('app.current_lodge_id', true))
        WITH CHECK (current_setting('app.is_super_admin', true)='true' OR lodge_id::text=current_setting('app.current_lodge_id', true))""")

def upgrade():
    op.add_column('staff_profiles',sa.Column('supervisor_staff_id',postgresql.UUID(as_uuid=True),nullable=True))
    op.add_column('staff_profiles',sa.Column('hire_date',sa.Date(),nullable=True))
    op.create_foreign_key('fk_staff_supervisor','staff_profiles','staff_profiles',['supervisor_staff_id'],['id'],ondelete='SET NULL')

    op.create_table('staff_leaves',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='CASCADE'),nullable=False),sa.Column('leave_type',sa.String(60),nullable=False),
        sa.Column('start_date',sa.Date(),nullable=False),sa.Column('end_date',sa.Date(),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('notes',sa.Text(),nullable=False),
        sa.Column('approved_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='SET NULL')),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('end_date >= start_date',name='ck_staff_leave_dates'))
    op.create_index('ix_staff_leaves_lodge_dates','staff_leaves',['lodge_id','start_date','end_date'])
    op.create_index('ix_staff_leaves_staff_id','staff_leaves',['staff_id'])

    op.create_table('staff_credentials',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='CASCADE'),nullable=False),sa.Column('credential_type',sa.String(100),nullable=False),sa.Column('name',sa.String(180),nullable=False),
        sa.Column('issuer',sa.String(180),nullable=False),sa.Column('reference_number',sa.String(120),nullable=False),sa.Column('issued_date',sa.Date()),sa.Column('expiry_date',sa.Date()),sa.Column('notes',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_staff_credentials_lodge_expiry','staff_credentials',['lodge_id','expiry_date'])
    op.create_index('ix_staff_credentials_staff_id','staff_credentials',['staff_id'])

    op.create_table('staff_training',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='CASCADE'),nullable=False),sa.Column('title',sa.String(200),nullable=False),sa.Column('provider',sa.String(180),nullable=False),
        sa.Column('completed_date',sa.Date()),sa.Column('renewal_due_date',sa.Date()),sa.Column('status',sa.String(30),nullable=False),sa.Column('notes',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_staff_training_lodge_staff','staff_training',['lodge_id','staff_id'])

    op.create_table('custom_roles',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('name',sa.String(120),nullable=False),sa.Column('base_role_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('roles.id',ondelete='RESTRICT'),nullable=False),sa.Column('description',sa.Text(),nullable=False),sa.Column('is_active',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('lodge_id','name',name='uq_custom_role_lodge_name'))
    op.create_index('ix_custom_roles_lodge_id','custom_roles',['lodge_id'])
    op.create_table('custom_role_permissions',
        sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('custom_role_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('custom_roles.id',ondelete='CASCADE'),primary_key=True),
        sa.Column('permission_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('permissions.id',ondelete='CASCADE'),primary_key=True))
    op.create_index('ix_custom_role_permissions_lodge_id','custom_role_permissions',['lodge_id'])
    op.add_column('memberships',sa.Column('custom_role_id',postgresql.UUID(as_uuid=True),nullable=True))
    op.create_foreign_key('fk_membership_custom_role','memberships','custom_roles',['custom_role_id'],['id'],ondelete='SET NULL')
    op.create_index('ix_memberships_custom_role_id','memberships',['custom_role_id'])

    op.add_column('tasks',sa.Column('recurrence_interval_days',sa.Integer(),nullable=True))
    op.add_column('tasks',sa.Column('recurrence_end_date',sa.Date(),nullable=True))
    op.create_table('task_checklist_items',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('task_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('tasks.id',ondelete='CASCADE'),nullable=False),sa.Column('label',sa.String(240),nullable=False),sa.Column('position',sa.Integer(),nullable=False),sa.Column('is_required',sa.Boolean(),nullable=False),
        sa.Column('completed_at',sa.DateTime(timezone=True)),sa.Column('completed_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='SET NULL')))
    op.create_index('ix_task_checklist_task','task_checklist_items',['task_id','position'])
    op.create_index('ix_task_checklist_lodge_id','task_checklist_items',['lodge_id'])
    op.create_table('task_comments',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('task_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('tasks.id',ondelete='CASCADE'),nullable=False),sa.Column('user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('body',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_task_comments_lodge_id','task_comments',['lodge_id'])
    op.create_index('ix_task_comments_task_id','task_comments',['task_id'])

    op.create_table('housekeeping_jobs',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('unit_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('units.id',ondelete='RESTRICT'),nullable=False),sa.Column('assigned_staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='SET NULL')),sa.Column('inspector_staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='SET NULL')),
        sa.Column('job_type',sa.String(40),nullable=False),sa.Column('status',sa.String(40),nullable=False),sa.Column('linen_notes',sa.Text(),nullable=False),sa.Column('notes',sa.Text(),nullable=False),sa.Column('due_at',sa.DateTime(timezone=True)),
        sa.Column('accepted_at',sa.DateTime(timezone=True)),sa.Column('started_at',sa.DateTime(timezone=True)),sa.Column('completed_at',sa.DateTime(timezone=True)),sa.Column('inspected_at',sa.DateTime(timezone=True)),
        sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_housekeeping_lodge_status_due','housekeeping_jobs',['lodge_id','status','due_at'])
    op.create_index('ix_housekeeping_jobs_unit_id','housekeeping_jobs',['unit_id'])
    op.create_index('ix_housekeeping_jobs_assigned_staff_id','housekeeping_jobs',['assigned_staff_id'])

    op.create_table('maintenance_assets',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),sa.Column('asset_code',sa.String(100),nullable=False),sa.Column('name',sa.String(180),nullable=False),sa.Column('category',sa.String(100),nullable=False),
        sa.Column('unit_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('units.id',ondelete='SET NULL')),sa.Column('vehicle_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('vehicles.id',ondelete='SET NULL')),sa.Column('status',sa.String(40),nullable=False),sa.Column('service_interval_days',sa.Integer()),sa.Column('next_service_date',sa.Date()),sa.Column('notes',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('lodge_id','asset_code',name='uq_asset_lodge_code'))
    op.create_index('ix_asset_lodge_status','maintenance_assets',['lodge_id','status'])
    op.add_column('maintenance_tickets',sa.Column('asset_id',postgresql.UUID(as_uuid=True),nullable=True))
    op.add_column('maintenance_tickets',sa.Column('scheduled_for',sa.DateTime(timezone=True),nullable=True))
    op.add_column('maintenance_tickets',sa.Column('downtime_started_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('maintenance_tickets',sa.Column('downtime_ended_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('maintenance_tickets',sa.Column('recurrence_interval_days',sa.Integer(),nullable=True))
    op.create_foreign_key('fk_maintenance_asset','maintenance_tickets','maintenance_assets',['asset_id'],['id'],ondelete='SET NULL')
    op.create_index('ix_maintenance_tickets_asset_id','maintenance_tickets',['asset_id'])
    op.create_table('maintenance_part_usage',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('maintenance_ticket_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('maintenance_tickets.id',ondelete='CASCADE'),nullable=False),sa.Column('part_name',sa.String(180),nullable=False),sa.Column('quantity',sa.Integer(),nullable=False),sa.Column('unit_cost_cents',sa.Integer(),nullable=False),sa.Column('notes',sa.Text(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('quantity > 0',name='ck_maintenance_part_quantity'),sa.CheckConstraint('unit_cost_cents >= 0',name='ck_maintenance_part_cost'))
    op.create_index('ix_maintenance_part_usage_lodge_id','maintenance_part_usage',['lodge_id'])
    op.create_index('ix_maintenance_part_usage_ticket','maintenance_part_usage',['maintenance_ticket_id'])

    for t in TENANT_TABLES:_rls(t)

    perms={
      'staff.hr.manage':'Manage leave, training and credentials','roles.custom.manage':'Create lodge custom roles and granular permissions',
      'housekeeping.view':'View housekeeping workflow','housekeeping.manage':'Manage housekeeping assignments and inspections',
      'housekeeping.own.manage':'Work on housekeeping jobs assigned to the current staff member','maintenance.assets.manage':'Manage lodge maintenance assets'
    }
    for k,d in perms.items():
        op.execute(sa.text("INSERT INTO permissions(id,key,description) VALUES(gen_random_uuid(),:k,:d) ON CONFLICT(key) DO NOTHING").bindparams(k=k,d=d))
    grants={
      'lodge_admin':list(perms.keys()),
      'department_manager':['staff.hr.manage','housekeeping.view','housekeeping.manage','maintenance.assets.manage'],
      'housekeeping':['housekeeping.view','housekeeping.own.manage'],
      'read_only':['housekeeping.view']
    }
    for role,ps in grants.items():
        for perm in ps:
            op.execute(sa.text("""INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r,permissions p WHERE r.key=:r AND p.key=:p ON CONFLICT DO NOTHING""").bindparams(r=role,p=perm))
    for plan in ['Standard','Premium']:
        for feature in ['staff_hr','custom_roles','advanced_tasks','housekeeping_full','maintenance_workshop']:
            op.execute(sa.text("INSERT INTO plan_entitlements(plan_key,feature_key,enabled) VALUES(:p,:f,true) ON CONFLICT(plan_key,feature_key) DO UPDATE SET enabled=true").bindparams(p=plan,f=feature))
    # Basic retains practical light versions but not advanced workflows.
    for feature in ['staff_hr','custom_roles','advanced_tasks','housekeeping_full','maintenance_workshop']:
        op.execute(sa.text("INSERT INTO plan_entitlements(plan_key,feature_key,enabled) VALUES('Basic',:f,false) ON CONFLICT(plan_key,feature_key) DO UPDATE SET enabled=false").bindparams(f=feature))

def downgrade():
    for table in reversed(TENANT_TABLES):
        op.execute(f'DROP POLICY IF EXISTS {table}_tenant_policy ON {table}')
    op.drop_table('maintenance_part_usage')
    op.drop_index('ix_maintenance_tickets_asset_id',table_name='maintenance_tickets')
    op.drop_constraint('fk_maintenance_asset','maintenance_tickets',type_='foreignkey')
    for c in ['recurrence_interval_days','downtime_ended_at','downtime_started_at','scheduled_for','asset_id']:
        op.drop_column('maintenance_tickets',c)
    op.drop_table('maintenance_assets')
    op.drop_table('housekeeping_jobs')
    op.drop_table('task_comments');op.drop_table('task_checklist_items')
    op.drop_column('tasks','recurrence_end_date');op.drop_column('tasks','recurrence_interval_days')
    op.drop_index('ix_memberships_custom_role_id',table_name='memberships');op.drop_constraint('fk_membership_custom_role','memberships',type_='foreignkey');op.drop_column('memberships','custom_role_id')
    op.drop_table('custom_role_permissions');op.drop_table('custom_roles')
    op.drop_table('staff_training');op.drop_table('staff_credentials');op.drop_table('staff_leaves')
    op.drop_constraint('fk_staff_supervisor','staff_profiles',type_='foreignkey');op.drop_column('staff_profiles','hire_date');op.drop_column('staff_profiles','supervisor_staff_id')
    for perm in ['staff.hr.manage','roles.custom.manage','housekeeping.view','housekeeping.manage','housekeeping.own.manage','maintenance.assets.manage']:
        op.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key=:p)").bindparams(p=perm));op.execute(sa.text("DELETE FROM permissions WHERE key=:p").bindparams(p=perm))
    for feature in ['staff_hr','custom_roles','advanced_tasks','housekeeping_full','maintenance_workshop']:
        op.execute(sa.text("DELETE FROM plan_entitlements WHERE feature_key=:f").bindparams(f=feature))
