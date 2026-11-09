"""Documented guest occasions, safari preferences and tenant-scoped communication log."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0023_guest_profiles"
down_revision = "0022_ai_reports"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("birthday", "anniversary"):
        op.add_column("guests", sa.Column(name, sa.Date(), nullable=True))
    op.add_column(
        "guests",
        sa.Column(
            "repeat_guest", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "guests",
        sa.Column("safari_preferences", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "guests", sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_unique_constraint("uq_guests_tenant", "guests", ["id", "lodge_id"])
    op.create_table(
        "guest_communications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lodge_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("lodges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("guest_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("client_reference", pg.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_by_user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["guest_id", "lodge_id"],
            ["guests.id", "guests.lodge_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "lodge_id",
            "guest_id",
            "client_reference",
            name="uq_guest_communication_reference",
        ),
        sa.CheckConstraint(
            "channel IN ('email','phone','in_person','whatsapp','other')",
            name="ck_guest_communication_channel",
        ),
        sa.CheckConstraint(
            "direction IN ('inbound','outbound','internal')",
            name="ck_guest_communication_direction",
        ),
    )
    op.create_index(
        "ix_guest_communications_lodge_id", "guest_communications", ["lodge_id"]
    )
    op.create_index(
        "ix_guest_communication_history",
        "guest_communications",
        ["lodge_id", "guest_id", "occurred_at", "id"],
    )
    op.execute("ALTER TABLE guest_communications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE guest_communications FORCE ROW LEVEL SECURITY")
    scope = "current_setting('app.is_super_admin',true)='true' OR lodge_id::text=current_setting('app.current_lodge_id',true)"
    op.execute(
        f"CREATE POLICY guest_communications_tenant ON guest_communications USING ({scope}) WITH CHECK ({scope})"
    )


def downgrade():
    op.drop_table("guest_communications")
    op.drop_constraint("uq_guests_tenant", "guests", type_="unique")
    for name in (
        "anonymized_at",
        "safari_preferences",
        "repeat_guest",
        "anniversary",
        "birthday",
    ):
        op.drop_column("guests", name)
