"""notifications, delivery outbox and operations intelligence"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='0004_operations_intelligence'
down_revision='0003_safari_operations'
branch_labels=None
depends_on=None

TENANT_TABLES=['notifications','notification_recipients','notification_preferences','notification_deliveries']

def upgrade():
    op.create_table('notifications',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('notification_type',sa.String(100),nullable=False),
        sa.Column('severity',sa.String(20),nullable=False,server_default='normal'),
        sa.Column('title',sa.String(240),nullable=False),
        sa.Column('body',sa.Text(),nullable=False,server_default=''),
        sa.Column('resource_type',sa.String(80),nullable=False,server_default=''),
        sa.Column('resource_id',sa.String(80),nullable=False,server_default=''),
        sa.Column('dedupe_key',sa.String(240)),
        sa.Column('created_by_event_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('operational_events.id',ondelete='SET NULL')),
        sa.Column('expires_at',sa.DateTime(timezone=True)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('lodge_id','dedupe_key',name='uq_notification_lodge_dedupe'),
        sa.CheckConstraint("severity in ('low','normal','high','critical')",name='ck_notification_severity'))
    op.create_index('ix_notifications_lodge_id','notifications',['lodge_id'])
    op.create_index('ix_notifications_notification_type','notifications',['notification_type'])
    op.create_index('ix_notifications_created_at','notifications',['created_at'])
    op.create_index('ix_notifications_lodge_created','notifications',['lodge_id','created_at'])
    op.create_index('ix_notifications_lodge_severity','notifications',['lodge_id','severity'])

    op.create_table('notification_recipients',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('notification_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('notifications.id',ondelete='CASCADE'),nullable=False),
        sa.Column('user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('read_at',sa.DateTime(timezone=True)),
        sa.Column('archived_at',sa.DateTime(timezone=True)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('notification_id','user_id',name='uq_notification_recipient'))
    op.create_index('ix_notification_recipients_lodge_id','notification_recipients',['lodge_id'])
    op.create_index('ix_notification_recipients_notification_id','notification_recipients',['notification_id'])
    op.create_index('ix_notification_recipients_user_id','notification_recipients',['user_id'])
    op.create_index('ix_notification_recipients_user_unread','notification_recipients',['user_id','read_at'])

    op.create_table('notification_preferences',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('email_enabled',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('email_min_severity',sa.String(20),nullable=False,server_default='high'),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('lodge_id','user_id',name='uq_notification_preference_user_lodge'),
        sa.CheckConstraint("email_min_severity in ('low','normal','high','critical')",name='ck_notification_pref_severity'))
    op.create_index('ix_notification_preferences_lodge_id','notification_preferences',['lodge_id'])
    op.create_index('ix_notification_preferences_user_id','notification_preferences',['user_id'])

    op.create_table('notification_deliveries',
        sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column('lodge_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),
        sa.Column('notification_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('notifications.id',ondelete='CASCADE'),nullable=False),
        sa.Column('user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('channel',sa.String(20),nullable=False,server_default='email'),
        sa.Column('destination',sa.String(320),nullable=False),
        sa.Column('idempotency_key',sa.String(240),nullable=False),
        sa.Column('status',sa.String(20),nullable=False,server_default='pending'),
        sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('next_attempt_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('last_error',sa.Text(),nullable=False,server_default=''),
        sa.Column('sent_at',sa.DateTime(timezone=True)),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('idempotency_key',name='uq_notification_delivery_idempotency'),
        sa.CheckConstraint("channel in ('email')",name='ck_notification_delivery_channel'),
        sa.CheckConstraint("status in ('pending','sending','sent','failed','dead')",name='ck_notification_delivery_status'))
    op.create_index('ix_notification_deliveries_lodge_id','notification_deliveries',['lodge_id'])
    op.create_index('ix_notification_deliveries_notification_id','notification_deliveries',['notification_id'])
    op.create_index('ix_notification_deliveries_user_id','notification_deliveries',['user_id'])
    op.create_index('ix_notification_deliveries_status','notification_deliveries',['status'])
    op.create_index('ix_notification_deliveries_next_attempt_at','notification_deliveries',['next_attempt_at'])
    op.create_index('ix_notification_deliveries_due','notification_deliveries',['status','next_attempt_at'])

    for table in TENANT_TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f'''CREATE POLICY {table}_tenant_policy ON {table} USING (current_setting('app.is_super_admin', true)='true' OR lodge_id::text = current_setting('app.current_lodge_id', true)) WITH CHECK (current_setting('app.is_super_admin', true)='true' OR lodge_id::text = current_setting('app.current_lodge_id', true))''')

    permissions={
        'notifications.view':'View personal system notifications',
        'notifications.manage':'Manage personal notification preferences and acknowledgement',
        'notifications.delivery.view':'View notification delivery audit records',
        'memory.view':'View lodge operational event history',
    }
    for key,desc in permissions.items():
        op.execute(sa.text("INSERT INTO permissions (id,key,description) VALUES (gen_random_uuid(),:k,:d) ON CONFLICT (key) DO NOTHING").bindparams(k=key,d=desc))
    role_map={
        'lodge_admin':['notifications.view','notifications.manage','notifications.delivery.view','memory.view'],
        'department_manager':['notifications.view','notifications.manage','memory.view'],
        'front_office':['notifications.view','notifications.manage','memory.view'],
        'ranger':['notifications.view','notifications.manage','memory.view'],
        'housekeeping':['notifications.view','notifications.manage'],
        'maintenance':['notifications.view','notifications.manage','memory.view'],
        'driver':['notifications.view','notifications.manage'],
        'fb':['notifications.view','notifications.manage'],
        'finance':['notifications.view','notifications.manage','memory.view'],
        'general_staff':['notifications.view','notifications.manage'],
        'read_only':['notifications.view','memory.view'],
    }
    for role_key,perm_keys in role_map.items():
        for perm in perm_keys:
            op.execute(sa.text("""INSERT INTO role_permissions(role_id,permission_id)
                SELECT r.id,p.id FROM roles r,permissions p WHERE r.key=:r AND p.key=:p
                ON CONFLICT DO NOTHING""").bindparams(r=role_key,p=perm))

def downgrade():
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key IN ('notifications.view','notifications.manage','notifications.delivery.view','memory.view'))")
    op.execute("DELETE FROM permissions WHERE key IN ('notifications.view','notifications.manage','notifications.delivery.view','memory.view')")
    op.drop_table('notification_deliveries')
    op.drop_table('notification_preferences')
    op.drop_table('notification_recipients')
    op.drop_table('notifications')
