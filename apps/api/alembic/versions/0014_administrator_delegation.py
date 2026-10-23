"""Make existing administrator management capabilities explicit for preset copying.

These narrow actions already have broader admin equivalents. No tenant/scope
policy or sensitive custom-role restriction is changed.
"""
from alembic import op
revision='0014_administrator_delegation'
down_revision='0013_lodge_display_preferences'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("""INSERT INTO role_permissions(role_id,permission_id)
    SELECT r.id,p.id FROM roles r CROSS JOIN permissions p
    WHERE r.key IN ('lodge_admin','group_admin')
    AND p.key IN ('tasks.own.manage','requests.own.manage','maintenance.report')
    ON CONFLICT DO NOTHING""")

def downgrade():
    op.execute("""DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE key IN ('lodge_admin','group_admin'))
    AND permission_id IN (SELECT id FROM permissions WHERE key IN ('tasks.own.manage','requests.own.manage','maintenance.report'))""")
