"""Private, expiring AI action proposals and one-time confirmations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0021_ai_actions"
down_revision = "0020_group_ai_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_actions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lodge_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("lodges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("conversation_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        *[
            sa.Column(k, pg.JSONB(), nullable=False)
            for k in ("payload", "preview", "snapshot")
        ],
        sa.Column("access_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("result", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id", "lodge_id", "user_id"],
            [
                "ai_conversations.id",
                "ai_conversations.lodge_id",
                "ai_conversations.user_id",
            ],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "conversation_id", "request_id", name="uq_ai_action_request"
        ),
        sa.CheckConstraint(
            "status IN ('pending','confirmed','cancelled')", name="ck_ai_action_status"
        ),
        sa.CheckConstraint(
            "action IN ('create_task','update_task','create_maintenance','create_housekeeping')",
            name="ck_ai_action_kind",
        ),
    )
    op.create_index(
        "ix_ai_action_owner", "ai_actions", ["lodge_id", "user_id", "created_at"]
    )
    op.execute("ALTER TABLE ai_actions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ai_actions FORCE ROW LEVEL SECURITY")
    scope = "lodge_id::text=current_setting('app.current_lodge_id',true) AND user_id::text=current_setting('app.current_user_id',true)"
    op.execute(
        f"CREATE POLICY ai_actions_private ON ai_actions USING ({scope}) WITH CHECK ({scope})"
    )
    op.execute(
        "INSERT INTO permissions(id,key,description) VALUES(gen_random_uuid(),'ai.actions','Review and confirm permitted AI action proposals') ON CONFLICT(key) DO NOTHING"
    )
    op.execute(
        "INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r,permissions p WHERE r.key IN ('lodge_admin','group_admin') AND p.key='ai.actions' ON CONFLICT DO NOTHING"
    )


def downgrade():
    op.drop_table("ai_actions")
    for table in ["role_permissions", "custom_role_permissions"]:
        op.execute(
            f"DELETE FROM {table} WHERE permission_id IN (SELECT id FROM permissions WHERE key='ai.actions')"
        )
    op.execute("DELETE FROM permissions WHERE key='ai.actions'")
