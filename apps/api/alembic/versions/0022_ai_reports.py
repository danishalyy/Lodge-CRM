"""Private actor-bound daily/weekly report schedules and durable run leases."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0022_ai_reports"
down_revision = "0021_ai_actions"
branch_labels = None
depends_on = None


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


def upgrade():
    op.add_column(
        "ai_conversations",
        sa.Column("origin", sa.String(10), nullable=False, server_default="chat"),
    )
    op.create_check_constraint(
        "ck_ai_conversation_origin", "ai_conversations", "origin IN ('chat','report')"
    )
    op.create_table(
        "ai_report_schedules",
        *common(),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("scope_type", sa.String(10), nullable=False),
        sa.Column(
            "group_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("lodge_groups.id", ondelete="CASCADE"),
            nullable=True,
        ),
        *[
            sa.Column(k, sa.Integer(), nullable=False)
            for k in ("hour", "minute", "weekday")
        ],
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("access_fingerprint", sa.String(64), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "lodge_id", "user_id", name="uq_ai_schedule_scope"),
        sa.UniqueConstraint(
            "lodge_id",
            "user_id",
            "scope_type",
            "kind",
            name="uq_ai_schedule_owner_kind",
        ),
        sa.CheckConstraint("kind IN ('daily','weekly')", name="ck_ai_schedule_kind"),
        sa.CheckConstraint(
            "(scope_type='lodge' AND group_id IS NULL) OR (scope_type='group' AND group_id IS NOT NULL)",
            name="ck_ai_schedule_scope",
        ),
        sa.CheckConstraint(
            "hour>=0 AND hour<=23 AND minute>=0 AND minute<=59 AND weekday>=0 AND weekday<=6",
            name="ck_ai_schedule_clock",
        ),
    )
    op.create_table(
        "ai_report_runs",
        *common(),
        sa.Column("schedule_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("slot_key", sa.String(80), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("access_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("insights", pg.JSONB(), nullable=False, server_default="[]"),
        sa.ForeignKeyConstraint(
            ["schedule_id", "lodge_id", "user_id"],
            [
                "ai_report_schedules.id",
                "ai_report_schedules.lodge_id",
                "ai_report_schedules.user_id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id", "lodge_id", "user_id"],
            [
                "ai_conversations.id",
                "ai_conversations.lodge_id",
                "ai_conversations.user_id",
            ],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("schedule_id", "slot_key", name="uq_ai_report_slot"),
        sa.CheckConstraint(
            "status IN ('queued','running','complete','failed','cancelled')",
            name="ck_ai_report_status",
        ),
    )
    op.create_index("ix_ai_report_due", "ai_report_runs", ["status", "next_attempt_at"])
    op.create_index(
        "ix_ai_report_owner", "ai_report_runs", ["lodge_id", "user_id", "created_at"]
    )
    for table in ["ai_report_schedules", "ai_report_runs"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        scope = "lodge_id::text=current_setting('app.current_lodge_id',true) AND user_id::text=current_setting('app.current_user_id',true)"
        op.execute(
            f"CREATE POLICY {table}_private ON {table} USING ({scope}) WITH CHECK ({scope})"
        )
    op.execute(
        "INSERT INTO permissions(id,key,description) VALUES(gen_random_uuid(),'ai.reports.manage','Manage and read private AI report schedules') ON CONFLICT(key) DO NOTHING"
    )
    op.execute(
        "INSERT INTO role_permissions(role_id,permission_id) SELECT r.id,p.id FROM roles r,permissions p WHERE r.key IN ('lodge_admin','group_admin') AND p.key='ai.reports.manage' ON CONFLICT DO NOTHING"
    )


def downgrade():
    op.execute(
        """DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=current_user AND (rolsuper OR rolbypassrls)) THEN RAISE EXCEPTION 'AI report downgrade requires a privileged migration administrator'; END IF; END $$"""
    )
    op.execute("DELETE FROM ai_conversations WHERE origin='report'")
    op.drop_table("ai_report_runs")
    op.drop_table("ai_report_schedules")
    op.drop_constraint("ck_ai_conversation_origin", "ai_conversations", type_="check")
    op.drop_column("ai_conversations", "origin")
    for table in ["role_permissions", "custom_role_permissions"]:
        op.execute(
            f"DELETE FROM {table} WHERE permission_id IN (SELECT id FROM permissions WHERE key='ai.reports.manage')"
        )
    op.execute("DELETE FROM permissions WHERE key='ai.reports.manage'")
