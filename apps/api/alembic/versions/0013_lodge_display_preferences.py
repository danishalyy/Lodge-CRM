"""Lodge date and currency preferences, managed by lodge/group administrators."""
from alembic import op
import sqlalchemy as sa
revision='0013_lodge_display_preferences'
down_revision='0012_mfa_recovery_codes'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('lodges',sa.Column('date_format',sa.String(20),nullable=False,server_default='locale'))
    op.add_column('lodges',sa.Column('currency',sa.String(3),nullable=False,server_default='ZAR'))
    op.create_check_constraint('ck_lodge_date_format','lodges',"date_format IN ('locale','dd/MM/yyyy','MM/dd/yyyy','yyyy-MM-dd')")
    op.execute("INSERT INTO permissions(id,key,description) VALUES(gen_random_uuid(),'lodge.settings.manage','Manage lodge display preferences')")
    op.execute("INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r,permissions p WHERE r.key IN ('lodge_admin','group_admin') AND p.key='lodge.settings.manage'")

def downgrade():
    op.execute("DELETE FROM custom_role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key='lodge.settings.manage')")
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE key='lodge.settings.manage')")
    op.execute("DELETE FROM permissions WHERE key='lodge.settings.manage'")
    op.drop_constraint('ck_lodge_date_format','lodges',type_='check')
    op.drop_column('lodges','currency')
    op.drop_column('lodges','date_format')
