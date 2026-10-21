"""Restore explicitly assigned multi-lodge groups without widening staff access."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='0011_lodge_groups'
down_revision='0010_account_email_delivery'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('lodge_groups',sa.Column('id',postgresql.UUID(as_uuid=True),primary_key=True),sa.Column('name',sa.String(180),nullable=False,unique=True),sa.Column('admin_user_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),sa.Column('is_active',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_lodge_groups_admin_user_id','lodge_groups',['admin_user_id'])
    op.add_column('lodges',sa.Column('group_id',postgresql.UUID(as_uuid=True),sa.ForeignKey('lodge_groups.id',ondelete='SET NULL'),nullable=True))
    op.create_index('ix_lodges_group_id','lodges',['group_id'])
    op.execute("INSERT INTO roles(id,key,name,description) VALUES(gen_random_uuid(),'group_admin','Group Admin','Administers only lodges explicitly assigned to their group')")
    op.execute("INSERT INTO role_permissions(role_id,permission_id) SELECT g.id,rp.permission_id FROM roles g CROSS JOIN role_permissions rp JOIN roles a ON a.id=rp.role_id WHERE g.key='group_admin' AND a.key='lodge_admin'")
    op.drop_constraint('uq_membership_one_lodge_per_user','memberships',type_='unique')
    # Serialize on the user row; check all memberships, including rows hidden by tenant RLS.
    op.execute("""CREATE FUNCTION public.validate_membership_scope() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE role_key text;
    BEGIN
      PERFORM 1 FROM public.users WHERE id=NEW.user_id FOR UPDATE;
      SELECT key INTO role_key FROM public.roles WHERE id=NEW.role_id;
      IF role_key='group_admin' THEN
        IF NOT EXISTS(SELECT 1 FROM public.lodges l JOIN public.lodge_groups g ON g.id=l.group_id WHERE l.id=NEW.lodge_id AND g.admin_user_id=NEW.user_id AND g.is_active) OR EXISTS(SELECT 1 FROM public.memberships m JOIN public.roles r ON r.id=m.role_id WHERE m.user_id=NEW.user_id AND m.id<>NEW.id AND r.key<>'group_admin') THEN
          RAISE EXCEPTION 'Group membership requires an assigned active group' USING ERRCODE='23514',CONSTRAINT='ck_membership_group_assignment';
        END IF;
      ELSIF EXISTS(SELECT 1 FROM public.memberships WHERE user_id=NEW.user_id AND id<>NEW.id AND lodge_id<>NEW.lodge_id) THEN
        RAISE EXCEPTION 'Ordinary accounts belong to one lodge' USING ERRCODE='23505',CONSTRAINT='uq_membership_one_lodge_per_user';
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER membership_scope_guard BEFORE INSERT OR UPDATE OF user_id,lodge_id,role_id ON memberships FOR EACH ROW EXECUTE FUNCTION public.validate_membership_scope()')
    op.execute('ALTER TABLE lodge_groups ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE lodge_groups FORCE ROW LEVEL SECURITY')
    op.execute("CREATE POLICY lodge_groups_read ON lodge_groups FOR SELECT USING(current_setting('app.is_super_admin',true)='true' OR admin_user_id::text=current_setting('app.current_user_id',true))")
    op.execute("CREATE POLICY lodge_groups_write ON lodge_groups FOR ALL USING(current_setting('app.is_super_admin',true)='true') WITH CHECK(current_setting('app.is_super_admin',true)='true')")

def downgrade():
    # Refuse to silently remove real multi-lodge account assignments.
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM memberships GROUP BY user_id HAVING COUNT(*)>1) THEN RAISE EXCEPTION 'Remove multi-lodge memberships before downgrading'; END IF; END $$")
    op.execute('DROP TRIGGER membership_scope_guard ON memberships')
    op.execute('DROP FUNCTION public.validate_membership_scope()')
    op.create_unique_constraint('uq_membership_one_lodge_per_user','memberships',['user_id'])
    op.execute("DELETE FROM role_permissions WHERE role_id IN(SELECT id FROM roles WHERE key='group_admin')")
    op.execute("DELETE FROM roles WHERE key='group_admin'")
    op.drop_column('lodges','group_id')
    op.drop_table('lodge_groups')
