"""Tenant-scoped, payload-free transactional invalidation outbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
revision = '0025_live_events'
down_revision = '0024_task_history'
branch_labels = depends_on = None
TABLES = {'tasks':'task','guest_requests':'request','units':'room','stays':'stay','maintenance_tickets':'maintenance','housekeeping_jobs':'housekeeping','notifications':'notification','notification_recipients':'notification','subscriptions':'subscription','task_checklist_items':'task','task_comments':'task','task_attachments':'task'}
def upgrade():
    op.create_table('live_events',sa.Column('id',sa.BigInteger(),sa.Identity(),primary_key=True),sa.Column('lodge_id',pg.UUID(as_uuid=True),sa.ForeignKey('lodges.id',ondelete='CASCADE'),nullable=False),sa.Column('entity',sa.String(24),nullable=False),sa.Column('entity_id',pg.UUID(as_uuid=True),nullable=False),sa.Column('kind',sa.String(40),nullable=False),sa.Column('version',pg.UUID(as_uuid=True),server_default=sa.text('gen_random_uuid()'),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('clock_timestamp()'),nullable=False))
    op.create_index('ix_live_events_lodge_cursor','live_events',['lodge_id','id'])
    op.create_index('ix_live_events_retention','live_events',['created_at'])
    op.execute("""ALTER TABLE live_events ENABLE ROW LEVEL SECURITY;
      ALTER TABLE live_events FORCE ROW LEVEL SECURITY;
      CREATE POLICY live_events_tenant ON live_events USING (current_setting('app.is_super_admin',true)='true' OR lodge_id=nullif(current_setting('app.current_lodge_id',true),'')::uuid)
      WITH CHECK (current_setting('app.is_super_admin',true)='true' OR lodge_id=nullif(current_setting('app.current_lodge_id',true),'')::uuid);
      CREATE FUNCTION record_live_change() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER AS $$
      DECLARE resource uuid; action text; BEGIN
        IF TG_OP='UPDATE' AND (to_jsonb(NEW)-'updated_at') IS NOT DISTINCT FROM (to_jsonb(OLD)-'updated_at') THEN RETURN NEW; END IF;
        resource=nullif(to_jsonb(NEW)->>'id','')::uuid;
        IF TG_TABLE_NAME='subscriptions' THEN resource=NEW.lodge_id;
        ELSIF TG_TABLE_NAME='notification_recipients' THEN resource=NEW.notification_id;
        ELSIF TG_TABLE_NAME IN ('task_checklist_items','task_comments','task_attachments') THEN resource=NEW.task_id; END IF;
        action=TG_ARGV[0]||CASE WHEN TG_OP='INSERT' AND TG_TABLE_NAME IN ('tasks','guest_requests','stays','maintenance_tickets','housekeeping_jobs','units') THEN '.created' ELSE '.updated' END;
        IF TG_TABLE_NAME='tasks' AND TG_OP='UPDATE' THEN
          IF NEW.assigned_staff_id IS DISTINCT FROM OLD.assigned_staff_id THEN action='task.assigned'; END IF;
        END IF;
        -- Deferred until commit: serial allocation must follow commit order within
        -- this lodge, otherwise a resumed stream could skip a late commit.
        PERFORM pg_advisory_xact_lock(hashtextextended('live-events:'||NEW.lodge_id::text,0));
        INSERT INTO live_events(lodge_id,entity,entity_id,kind) VALUES(NEW.lodge_id,TG_ARGV[0],resource,action);
        RETURN NEW;
      END; $$;""")
    for table,entity in TABLES.items():
        op.execute(f"CREATE CONSTRAINT TRIGGER trg_live_{table} AFTER INSERT OR UPDATE ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION record_live_change('{entity}')")
def downgrade():
    for table in TABLES:op.execute(f'DROP TRIGGER trg_live_{table} ON {table}')
    op.execute('DROP FUNCTION record_live_change()')
    op.drop_table('live_events')
