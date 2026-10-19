"""production operational core

Revision ID: 0002_operational_core
Revises: 0001_prod_foundation
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='0002_operational_core'
down_revision='0001_prod_foundation'
branch_labels=None
depends_on=None

TENANT_TABLES=['invitations','departments','staff_profiles','units','guests','stays','tasks','guest_requests','maintenance_tickets','operational_events']


def upgrade():
    op.create_table('invitations',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('token_hash',sa.String(64),nullable=False,unique=True),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('used_at',sa.DateTime(timezone=True)),
        sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='SET NULL')),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_invitations_lodge_id','invitations',['lodge_id']); op.create_index('ix_invitations_user_id','invitations',['user_id']); op.create_index('ix_invitations_token_hash','invitations',['token_hash'],unique=True); op.create_index('ix_invitations_expires_at','invitations',['expires_at'])

    op.create_table('departments',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True), sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('name',sa.String(120),nullable=False), sa.Column('description',sa.Text(),nullable=False,server_default=''), sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.true()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False), sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False), sa.UniqueConstraint('lodge_id','name',name='uq_department_lodge_name'))
    op.create_index('ix_departments_lodge_id','departments',['lodge_id']); op.create_index('ix_departments_lodge_active','departments',['lodge_id','is_active'])

    op.create_table('staff_profiles',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True), sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='SET NULL')), sa.Column('department_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('departments.id',ondelete='SET NULL')),
        sa.Column('employee_code',sa.String(80)), sa.Column('full_name',sa.String(180),nullable=False), sa.Column('email',sa.String(320)), sa.Column('phone',sa.String(80),nullable=False,server_default=''),
        sa.Column('job_title',sa.String(160),nullable=False,server_default=''), sa.Column('employment_status',sa.String(30),nullable=False,server_default='active'), sa.Column('operational_status',sa.String(30),nullable=False,server_default='available'),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False), sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False), sa.UniqueConstraint('lodge_id','employee_code',name='uq_staff_lodge_code'),
        sa.CheckConstraint("employment_status in ('active','inactive','leave')",name='ck_staff_employment_status'), sa.CheckConstraint("operational_status in ('available','on_shift','on_drive','off_duty','leave')",name='ck_staff_operational_status'))
    op.create_index('ix_staff_profiles_lodge_id','staff_profiles',['lodge_id']); op.create_index('ix_staff_profiles_user_id','staff_profiles',['user_id']); op.create_index('ix_staff_profiles_department_id','staff_profiles',['department_id']); op.create_index('ix_staff_lodge_status','staff_profiles',['lodge_id','employment_status'])

    op.create_table('units',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True), sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('name',sa.String(160),nullable=False), sa.Column('unit_type',sa.String(80),nullable=False,server_default='Room'), sa.Column('status',sa.String(40),nullable=False,server_default='vacant'), sa.Column('notes',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False), sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False), sa.UniqueConstraint('lodge_id','name',name='uq_unit_lodge_name'),
        sa.CheckConstraint("status in ('vacant','occupied','needs_cleaning','cleaning','inspection','ready','maintenance','out_of_service')",name='ck_unit_status'))
    op.create_index('ix_units_lodge_id','units',['lodge_id']); op.create_index('ix_units_lodge_status','units',['lodge_id','status'])

    op.create_table('guests',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True), sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('first_name',sa.String(120),nullable=False), sa.Column('last_name',sa.String(120),nullable=False), sa.Column('email',sa.String(320)), sa.Column('phone',sa.String(80),nullable=False,server_default=''), sa.Column('nationality',sa.String(120),nullable=False,server_default=''),
        sa.Column('vip',sa.Boolean(),nullable=False,server_default=sa.false()), sa.Column('dietary_requirements',sa.Text(),nullable=False,server_default=''), sa.Column('allergies',sa.Text(),nullable=False,server_default=''), sa.Column('preferences',sa.Text(),nullable=False,server_default=''), sa.Column('notes',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False), sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_guests_lodge_id','guests',['lodge_id']); op.create_index('ix_guests_lodge_name','guests',['lodge_id','last_name','first_name'])

    op.create_table('stays',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True), sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('guest_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('guests.id',ondelete='RESTRICT'),nullable=False), sa.Column('unit_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('units.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('arrival_date',sa.Date(),nullable=False), sa.Column('departure_date',sa.Date(),nullable=False), sa.Column('party_size',sa.Integer(),nullable=False,server_default='1'), sa.Column('status',sa.String(30),nullable=False,server_default='upcoming'),
        sa.Column('expected_arrival_time',sa.String(10),nullable=False,server_default=''), sa.Column('expected_departure_time',sa.String(10),nullable=False,server_default=''), sa.Column('transfer_notes',sa.Text(),nullable=False,server_default=''), sa.Column('special_requirements',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False), sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('departure_date >= arrival_date',name='ck_stay_dates'), sa.CheckConstraint('party_size >= 1',name='ck_stay_party_size'), sa.CheckConstraint("status in ('upcoming','arriving','in_house','departing','completed','cancelled')",name='ck_stay_status'))
    op.create_index('ix_stays_lodge_id','stays',['lodge_id']); op.create_index('ix_stays_guest_id','stays',['guest_id']); op.create_index('ix_stays_unit_id','stays',['unit_id']); op.create_index('ix_stays_lodge_dates','stays',['lodge_id','arrival_date','departure_date'])

    op.create_table('tasks',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True), sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('title',sa.String(240),nullable=False), sa.Column('description',sa.Text(),nullable=False,server_default=''), sa.Column('department_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('departments.id',ondelete='SET NULL')), sa.Column('assigned_staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='SET NULL')),
        sa.Column('guest_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('guests.id',ondelete='SET NULL')), sa.Column('unit_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('units.id',ondelete='SET NULL')),
        sa.Column('priority',sa.String(20),nullable=False,server_default='normal'), sa.Column('status',sa.String(30),nullable=False,server_default='created'), sa.Column('due_at',sa.DateTime(timezone=True)),
        sa.Column('accepted_at',sa.DateTime(timezone=True)), sa.Column('started_at',sa.DateTime(timezone=True)), sa.Column('completed_at',sa.DateTime(timezone=True)), sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False), sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("priority in ('low','normal','high','critical')",name='ck_task_priority'), sa.CheckConstraint("status in ('created','assigned','accepted','started','completed','cancelled')",name='ck_task_status'))
    op.create_index('ix_tasks_lodge_id','tasks',['lodge_id']); op.create_index('ix_tasks_department_id','tasks',['department_id']); op.create_index('ix_tasks_assigned_staff_id','tasks',['assigned_staff_id']); op.create_index('ix_tasks_lodge_status_due','tasks',['lodge_id','status','due_at'])

    op.create_table('guest_requests',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True), sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False), sa.Column('guest_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('guests.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('stay_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('stays.id',ondelete='SET NULL')), sa.Column('department_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('departments.id',ondelete='SET NULL')), sa.Column('assigned_staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='SET NULL')), sa.Column('task_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('tasks.id',ondelete='SET NULL')),
        sa.Column('request_type',sa.String(80),nullable=False), sa.Column('description',sa.Text(),nullable=False), sa.Column('priority',sa.String(20),nullable=False,server_default='normal'), sa.Column('status',sa.String(30),nullable=False,server_default='open'), sa.Column('resolution',sa.Text(),nullable=False,server_default=''), sa.Column('resolved_at',sa.DateTime(timezone=True)), sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False), sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False), sa.CheckConstraint("priority in ('low','normal','high','critical')",name='ck_request_priority'), sa.CheckConstraint("status in ('open','assigned','in_progress','waiting','resolved','cancelled')",name='ck_request_status'))
    op.create_index('ix_guest_requests_lodge_id','guest_requests',['lodge_id']); op.create_index('ix_guest_requests_guest_id','guest_requests',['guest_id']); op.create_index('ix_requests_lodge_status','guest_requests',['lodge_id','status'])

    op.create_table('maintenance_tickets',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True), sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False), sa.Column('title',sa.String(240),nullable=False), sa.Column('description',sa.Text(),nullable=False,server_default=''), sa.Column('category',sa.String(80),nullable=False,server_default='general'),
        sa.Column('priority',sa.String(20),nullable=False,server_default='normal'), sa.Column('status',sa.String(30),nullable=False,server_default='open'), sa.Column('unit_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('units.id',ondelete='SET NULL')), sa.Column('assigned_staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='SET NULL')),
        sa.Column('cost_cents',sa.Integer()), sa.Column('resolution',sa.Text(),nullable=False,server_default=''), sa.Column('completed_at',sa.DateTime(timezone=True)), sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False), sa.Column('created_at',sa.DateTime(timezone=True),nullable=False), sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("priority in ('low','normal','high','critical')",name='ck_maintenance_priority'), sa.CheckConstraint("status in ('open','assigned','in_progress','waiting','completed','cancelled')",name='ck_maintenance_status'), sa.CheckConstraint('cost_cents is null or cost_cents >= 0',name='ck_maintenance_cost'))
    op.create_index('ix_maintenance_tickets_lodge_id','maintenance_tickets',['lodge_id']); op.create_index('ix_maintenance_lodge_status','maintenance_tickets',['lodge_id','status'])

    op.create_table('operational_events',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True), sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False), sa.Column('actor_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='SET NULL')), sa.Column('event_type',sa.String(120),nullable=False), sa.Column('resource_type',sa.String(80),nullable=False), sa.Column('resource_id',sa.String(80),nullable=False), sa.Column('summary',sa.String(300),nullable=False), sa.Column('detail',sa.Text(),nullable=False,server_default=''), sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_operational_events_lodge_id','operational_events',['lodge_id']); op.create_index('ix_operational_events_event_type','operational_events',['event_type']); op.create_index('ix_operational_events_created_at','operational_events',['created_at']); op.create_index('ix_events_lodge_created','operational_events',['lodge_id','created_at'])

    # Every tenant-bearing operational table is protected by RLS.
    for table in TENANT_TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'''CREATE POLICY {table}_tenant_policy ON {table} USING (current_setting('app.is_super_admin', true)='true' OR lodge_id::text = current_setting('app.current_lodge_id', true)) WITH CHECK (current_setting('app.is_super_admin', true)='true' OR lodge_id::text = current_setting('app.current_lodge_id', true))''')

    permissions={
      'departments.view':'View departments','departments.manage':'Create and update departments',
      'staff.view':'View staff','staff.manage':'Create and update staff profiles',
      'units.view':'View rooms and units','units.manage':'Create and update rooms and units',
      'guests.view':'View guest CRM','guests.manage':'Create and update guest CRM records',
      'stays.view':'View stays','stays.manage':'Create and update stays',
      'tasks.view':'View tasks','tasks.manage':'Create, assign and transition tasks',
      'requests.view':'View guest requests','requests.manage':'Create and resolve guest requests',
      'maintenance.view':'View maintenance','maintenance.manage':'Create and update maintenance tickets',
      'reports.view':'View operational reports'
    }
    for key,desc in permissions.items():
        op.execute(sa.text("INSERT INTO permissions (id,key,description) VALUES (gen_random_uuid(),:k,:d) ON CONFLICT (key) DO NOTHING").bindparams(k=key,d=desc))

    all_manage=list(permissions.keys())
    role_map={
      'lodge_admin':all_manage,
      'department_manager':['departments.view','staff.view','units.view','guests.view','stays.view','tasks.view','tasks.manage','requests.view','requests.manage','maintenance.view','maintenance.manage','reports.view'],
      'front_office':['departments.view','staff.view','units.view','guests.view','guests.manage','stays.view','stays.manage','tasks.view','tasks.manage','requests.view','requests.manage'],
      'ranger':['units.view','guests.view','stays.view','tasks.view','maintenance.view'],
      'housekeeping':['units.view','units.manage','guests.view','stays.view','tasks.view','requests.view','maintenance.view','maintenance.manage'],
      'maintenance':['units.view','staff.view','tasks.view','maintenance.view','maintenance.manage'],
      'driver':['guests.view','stays.view','tasks.view'],
      'fb':['guests.view','stays.view','tasks.view','requests.view'],
      'finance':['reports.view'],
      'general_staff':['tasks.view','requests.view'],
      'read_only':['departments.view','staff.view','units.view','guests.view','stays.view','tasks.view','requests.view','maintenance.view','reports.view']
    }
    for role_key,perm_keys in role_map.items():
        for perm in perm_keys:
            op.execute(sa.text("""INSERT INTO role_permissions(role_id,permission_id)
              SELECT r.id,p.id FROM roles r,permissions p WHERE r.key=:r AND p.key=:p
              ON CONFLICT DO NOTHING""").bindparams(r=role_key,p=perm))


def downgrade():
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key IN ('departments.view','departments.manage','staff.view','staff.manage','units.view','units.manage','guests.view','guests.manage','stays.view','stays.manage','tasks.view','tasks.manage','requests.view','requests.manage','maintenance.view','maintenance.manage','reports.view'))")
    op.execute("DELETE FROM permissions WHERE key IN ('departments.view','departments.manage','staff.view','staff.manage','units.view','units.manage','guests.view','guests.manage','stays.view','stays.manage','tasks.view','tasks.manage','requests.view','requests.manage','maintenance.view','maintenance.manage','reports.view')")
    for t in reversed(TENANT_TABLES):
        op.drop_table(t)
