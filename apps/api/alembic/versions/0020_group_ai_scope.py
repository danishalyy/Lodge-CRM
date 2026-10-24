"""Explicit private group conversation scope; retain owner/lodge FORCE RLS."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0020_group_ai_scope"
down_revision = "0019_private_knowledge"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ai_conversations",
        sa.Column("scope_type", sa.String(10), nullable=False, server_default="lodge"),
    )
    op.add_column(
        "ai_conversations",
        sa.Column(
            "group_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("lodge_groups.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_ai_conversation_scope",
        "ai_conversations",
        "(scope_type='lodge' AND group_id IS NULL) OR (scope_type='group' AND group_id IS NOT NULL)",
    )
    op.execute(
        "INSERT INTO permissions(id,key,description) VALUES(gen_random_uuid(),'ai.group.view','Compare explicitly assigned lodges with private Group Owner AI') ON CONFLICT(key) DO NOTHING"
    )
    op.execute(
        "INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r,permissions p WHERE r.key='group_admin' AND p.key='ai.group.view' ON CONFLICT DO NOTHING"
    )


def downgrade():
    # FORCE RLS applies to table owners too. Refuse a downgrade that cannot
    # delete ALL group histories; never leave hidden cross-property rows behind.
    op.execute(
        """DO $$ BEGIN IF NOT EXISTS (
      SELECT 1 FROM pg_roles WHERE rolname=current_user AND (rolsuper OR rolbypassrls))
      THEN RAISE EXCEPTION 'Group AI downgrade requires a privileged migration administrator';
      END IF; END $$"""
    )
    # Do not reinterpret a saved cross-property answer as a single-lodge answer.
    op.execute("DELETE FROM ai_conversations WHERE scope_type='group'")
    op.drop_constraint("ck_ai_conversation_scope", "ai_conversations", type_="check")
    op.drop_column("ai_conversations", "group_id")
    op.drop_column("ai_conversations", "scope_type")
    for table in ["custom_role_permissions", "role_permissions"]:
        op.execute(
            f"DELETE FROM {table} WHERE permission_id IN (SELECT id FROM permissions WHERE key='ai.group.view')"
        )
    op.execute("DELETE FROM permissions WHERE key='ai.group.view'")
