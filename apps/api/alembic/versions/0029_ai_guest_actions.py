"""Extend the explicit AI action allowlist without changing ownership or RLS."""

from alembic import op
import sqlalchemy as sa

revision = "0029_ai_guest_actions"
down_revision = "0028_email_sign_in"
branch_labels = depends_on = None

OLD = "'create_task','update_task','create_maintenance','create_housekeeping'"
NEW = (
    "'create_guest','create_stay','create_request','create_activity','create_transfer'"
)


def upgrade():
    op.drop_constraint("ck_ai_action_kind", "ai_actions", type_="check")
    op.create_check_constraint(
        "ck_ai_action_kind", "ai_actions", f"action IN ({OLD},{NEW})"
    )


def downgrade():
    # Never discard new proposals/audit history merely to fit an older executable.
    if op.get_bind().scalar(
        sa.text(f"SELECT EXISTS (SELECT 1 FROM ai_actions WHERE action IN ({NEW}))")
    ):
        raise RuntimeError(
            "Cannot downgrade AI actions while new action records exist; retain this schema/application or restore a matching pre-upgrade backup."
        )
    op.drop_constraint("ck_ai_action_kind", "ai_actions", type_="check")
    op.create_check_constraint("ck_ai_action_kind", "ai_actions", f"action IN ({OLD})")
