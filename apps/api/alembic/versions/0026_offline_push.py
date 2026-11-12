"""Atomic offline receipts and private opt-in browser push delivery."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0026_offline_push"
down_revision = "0025_live_events"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "offline_receipts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lodge_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lodges.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "push_preferences",
        sa.Column(
            "lodge_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lodges.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("categories", JSONB(), nullable=False),
    )
    op.create_table(
        "push_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lodge_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lodges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("auth_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("encrypted_subscription", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "push_deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lodge_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lodges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            UUID(as_uuid=True),
            sa.ForeignKey("push_subscriptions.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "notification_id",
            UUID(as_uuid=True),
            sa.ForeignKey("notifications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(40), server_default="", nullable=False),
        sa.UniqueConstraint(
            "subscription_id", "notification_id", name="uq_push_delivery_notice"
        ),
    )
    op.create_index(
        "ix_push_deliveries_due", "push_deliveries", ["status", "next_attempt_at"]
    )
    op.create_index(
        "ix_push_subscriptions_owner", "push_subscriptions", ["lodge_id", "user_id"]
    )
    for table in (
        "offline_receipts",
        "push_preferences",
        "push_subscriptions",
        "push_deliveries",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        check = (
            "lodge_id::text=current_setting('app.current_lodge_id',true)"
            if table == "push_deliveries"
            else "(lodge_id::text=current_setting('app.current_lodge_id',true) AND user_id::text=current_setting('app.current_user_id',true))"
        )
        op.execute(
            f"""CREATE POLICY {table}_owner ON {table} USING (
            current_setting('app.is_super_admin',true)='true' OR
            (lodge_id::text=current_setting('app.current_lodge_id',true) AND user_id::text=current_setting('app.current_user_id',true)))
            WITH CHECK (current_setting('app.is_super_admin',true)='true' OR {check})"""
        )


def downgrade():
    for table in (
        "push_deliveries",
        "push_subscriptions",
        "push_preferences",
        "offline_receipts",
    ):
        op.drop_table(table)
