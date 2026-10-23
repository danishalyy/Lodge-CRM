"""Private tenant/owner AI conversation, message, execution and usage records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0018_ai_foundation"
down_revision = "0017_south_africa_currency"
branch_labels = None
depends_on = None
TABLES = ["ai_conversations", "ai_messages", "ai_usage", "ai_tool_executions"]


def common():
    return [
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    ]


def conversation_fk():
    return sa.ForeignKeyConstraint(
        ["conversation_id", "lodge_id", "user_id"],
        [
            "ai_conversations.id",
            "ai_conversations.lodge_id",
            "ai_conversations.user_id",
        ],
        ondelete="CASCADE",
    )


def upgrade():
    op.create_table(
        "ai_conversations",
        *common(),
        sa.Column("access_fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "id", "lodge_id", "user_id", name="uq_ai_conversation_scope"
        ),
    )
    op.create_index(
        "ix_ai_conversation_owner",
        "ai_conversations",
        ["lodge_id", "user_id", "created_at"],
    )
    op.create_table(
        "ai_messages",
        *common(),
        sa.Column("conversation_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", pg.JSONB(), nullable=False, server_default="[]"),
        conversation_fk(),
        sa.UniqueConstraint(
            "conversation_id", "request_id", "role", name="uq_ai_message_turn_role"
        ),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_ai_message_role"),
    )
    op.create_index(
        "ix_ai_message_conversation", "ai_messages", ["conversation_id", "created_at"]
    )
    op.create_table(
        "ai_usage",
        *common(),
        sa.Column("conversation_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        *[
            sa.Column(k, sa.Integer(), nullable=False)
            for k in ["input_tokens", "output_tokens", "latency_ms", "tool_count"]
        ],
        sa.Column("error_code", sa.String(80), nullable=False),
        conversation_fk(),
        sa.UniqueConstraint(
            "conversation_id", "request_id", name="uq_ai_usage_request"
        ),
        sa.CheckConstraint(
            "status IN ('pending','complete','failed')", name="ck_ai_usage_status"
        ),
    )
    op.create_index(
        "ix_ai_usage_owner", "ai_usage", ["lodge_id", "user_id", "created_at"]
    )
    op.create_table(
        "ai_tool_executions",
        *common(),
        sa.Column("conversation_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        conversation_fk(),
    )
    op.create_index(
        "ix_ai_tool_conversation",
        "ai_tool_executions",
        ["conversation_id", "created_at"],
    )
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        scope = "lodge_id::text=current_setting('app.current_lodge_id',true) AND user_id::text=current_setting('app.current_user_id',true)"
        op.execute(
            f"CREATE POLICY {table}_private ON {table} USING ({scope}) WITH CHECK ({scope})"
        )
    op.execute(
        "INSERT INTO permissions(id,key,description) VALUES(gen_random_uuid(),'ai.use','Use permitted lodge AI tools and private conversations') ON CONFLICT(key) DO NOTHING"
    )
    op.execute(
        "INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r,permissions p WHERE r.key IN ('lodge_admin','group_admin') AND p.key='ai.use' ON CONFLICT DO NOTHING"
    )


def downgrade():
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute(
        "DELETE FROM custom_role_permissions WHERE permission_id IN(SELECT id FROM permissions WHERE key='ai.use')"
    )
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN(SELECT id FROM permissions WHERE key='ai.use')"
    )
    op.execute("DELETE FROM permissions WHERE key='ai.use'")
