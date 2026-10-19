"""core operations completion

Revision ID: 0007_core_ops_completion
Revises: 0006_operational_workflows
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='0007_core_ops_completion'
down_revision='0006_operational_workflows'
branch_labels=None
depends_on=None

TENANT_TABLES=['guest_feedback','staff_shifts','staff_incidents','staff_performance_notes','meal_services','meal_service_guests','task_attachments']

def _rls(table):
    op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
    op.execute(f"CREATE POLICY {table}_tenant_policy ON {table} USING (current_setting('app.is_super_admin', true) = 'true' OR lodge_id::text = current_setting('app.current_lodge_id', true)) WITH CHECK (current_setting('app.is_super_admin', true) = 'true' OR lodge_id::text = current_setting('app.current_lodge_id', true))")

def upgrade():
    op.create_table('guest_feedback',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('guest_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('guests.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('stay_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('stays.id',ondelete='SET NULL')),
        sa.Column('department_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('departments.id',ondelete='SET NULL')),
        sa.Column('assigned_staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='SET NULL')),
        sa.Column('feedback_type',sa.String(30),nullable=False),sa.Column('category',sa.String(100),nullable=False),sa.Column('rating',sa.Integer()),
        sa.Column('comments',sa.Text(),nullable=False),sa.Column('follow_up_required',sa.Boolean(),nullable=False),sa.Column('status',sa.String(30),nullable=False),
        sa.Column('resolution',sa.Text(),nullable=False),sa.Column('resolved_at',sa.DateTime(timezone=True)),
        sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('rating IS NULL OR (rating >= 1 AND rating <= 5)',name='ck_guest_feedback_rating'))
    op.create_index('ix_guest_feedback_lodge_status','guest_feedback',['lodge_id','status'])
    op.create_index('ix_guest_feedback_guest_created','guest_feedback',['guest_id','created_at'])

    op.create_table('staff_shifts',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='CASCADE'),nullable=False),sa.Column('starts_at',sa.DateTime(timezone=True),nullable=False),sa.Column('ends_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('status',sa.String(30),nullable=False),sa.Column('notes',sa.Text(),nullable=False),sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('ends_at > starts_at',name='ck_staff_shift_times'))
    op.create_index('ix_staff_shifts_lodge_start','staff_shifts',['lodge_id','starts_at'])
    op.create_index('ix_staff_shifts_staff_id','staff_shifts',['staff_id'])

    op.create_table('staff_incidents',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='CASCADE'),nullable=False),sa.Column('incident_type',sa.String(80),nullable=False),sa.Column('severity',sa.String(20),nullable=False),sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('description',sa.Text(),nullable=False),sa.Column('action_taken',sa.Text(),nullable=False),sa.Column('is_confidential',sa.Boolean(),nullable=False),sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_staff_incidents_lodge_date','staff_incidents',['lodge_id','occurred_at'])

    op.create_table('staff_performance_notes',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('staff_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('staff_profiles.id',ondelete='CASCADE'),nullable=False),sa.Column('note_type',sa.String(40),nullable=False),sa.Column('rating',sa.Integer()),sa.Column('notes',sa.Text(),nullable=False),sa.Column('review_date',sa.Date(),nullable=False),
        sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('rating IS NULL OR (rating >= 1 AND rating <= 5)',name='ck_staff_performance_rating'))
    op.create_index('ix_staff_performance_lodge_staff','staff_performance_notes',['lodge_id','staff_id'])

    op.create_table('meal_services',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('name',sa.String(160),nullable=False),sa.Column('meal_type',sa.String(40),nullable=False),sa.Column('scheduled_at',sa.DateTime(timezone=True),nullable=False),sa.Column('location',sa.String(180),nullable=False),sa.Column('expected_guest_count',sa.Integer(),nullable=False),sa.Column('status',sa.String(30),nullable=False),sa.Column('notes',sa.Text(),nullable=False),
        sa.Column('created_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint('expected_guest_count >= 0',name='ck_meal_guest_count'))
    op.create_index('ix_meal_services_lodge_time','meal_services',['lodge_id','scheduled_at'])
    op.create_table('meal_service_guests',
        sa.Column('meal_service_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('meal_services.id',ondelete='CASCADE'),primary_key=True),sa.Column('guest_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('guests.id',ondelete='CASCADE'),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),sa.Column('notes',sa.Text(),nullable=False),sa.UniqueConstraint('meal_service_id','guest_id',name='uq_meal_service_guest'))
    op.create_index('ix_meal_service_guests_lodge_id','meal_service_guests',['lodge_id'])

    op.create_table('task_attachments',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),sa.Column('task_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('tasks.id',ondelete='CASCADE'),nullable=False),
        sa.Column('object_key',sa.String(600),nullable=False),sa.Column('file_name',sa.String(240),nullable=False),sa.Column('content_type',sa.String(120),nullable=False),sa.Column('size_bytes',sa.Integer(),nullable=False),sa.Column('sha256',sa.String(64),nullable=False),sa.Column('uploaded_by_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('lodge_id','object_key',name='uq_task_attachment_object_key'),sa.CheckConstraint('size_bytes > 0',name='ck_task_attachment_size'))
    op.create_index('ix_task_attachments_task','task_attachments',['task_id','created_at'])
    op.create_index('ix_task_attachments_lodge_id','task_attachments',['lodge_id'])

    for t in TENANT_TABLES:_rls(t)

    perms={
      'feedback.view':'View guest feedback and complaints','feedback.manage':'Manage guest feedback and complaint follow-up',
      'staff.roster.manage':'Manage staff shifts and rosters','staff.performance.manage':'Manage staff incidents and performance notes',
      'fb.view':'View meal services and dietary requirements','fb.manage':'Manage meal services and kitchen operations'
    }
    for k,d in perms.items():
        op.execute(sa.text("INSERT INTO permissions(id,key,description) VALUES(gen_random_uuid(),:k,:d) ON CONFLICT(key) DO NOTHING").bindparams(k=k,d=d))
    grants={
      'lodge_admin':list(perms.keys()),'front_office':['feedback.view','feedback.manage'],
      'department_manager':['feedback.view','feedback.manage','staff.roster.manage','staff.performance.manage','fb.view','fb.manage'],
      'fb':['fb.view','fb.manage'],'read_only':['feedback.view','fb.view']
    }
    for role,ps in grants.items():
        for perm in ps:
            op.execute(sa.text("INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r,permissions p WHERE r.key=:r AND p.key=:p ON CONFLICT DO NOTHING").bindparams(r=role,p=perm))
    for plan in ['Standard','Premium']:
        for feature in ['guest_feedback','staff_roster','staff_performance','fb_operations','task_attachments']:
            op.execute(sa.text("INSERT INTO plan_entitlements(plan_key,feature_key,enabled) VALUES(:p,:f,true) ON CONFLICT(plan_key,feature_key) DO UPDATE SET enabled=true").bindparams(p=plan,f=feature))
    for feature in ['guest_feedback','staff_roster','staff_performance','fb_operations','task_attachments']:
        op.execute(sa.text("INSERT INTO plan_entitlements(plan_key,feature_key,enabled) VALUES('Basic',:f,false) ON CONFLICT(plan_key,feature_key) DO UPDATE SET enabled=false").bindparams(f=feature))

def downgrade():
    for t in reversed(TENANT_TABLES): op.execute(f'DROP POLICY IF EXISTS {t}_tenant_policy ON {t}')
    for t in ['task_attachments','meal_service_guests','meal_services','staff_performance_notes','staff_incidents','staff_shifts','guest_feedback']:
        op.drop_table(t)
    for perm in ['feedback.view','feedback.manage','staff.roster.manage','staff.performance.manage','fb.view','fb.manage']:
        op.execute(sa.text("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key=:p)").bindparams(p=perm));op.execute(sa.text("DELETE FROM permissions WHERE key=:p").bindparams(p=perm))
    for feature in ['guest_feedback','staff_roster','staff_performance','fb_operations','task_attachments']:
        op.execute(sa.text("DELETE FROM plan_entitlements WHERE feature_key=:f").bindparams(f=feature))
