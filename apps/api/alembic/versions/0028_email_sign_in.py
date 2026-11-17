"""Email sign-in challenges for non-platform identities; retain platform TOTP."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0028_email_sign_in"
down_revision = "0027_guest_portal"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "email_login_challenges",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column(
            "user_id",
            UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("code_hash", sa.String(64)),
        sa.Column("credential_digest", sa.String(64), nullable=False),
        sa.Column("realm", sa.String(12), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("realm IN ('staff','guest')", name="ck_email_login_realm"),
        sa.CheckConstraint(
            "attempts >= 0 AND attempts <= 5", name="ck_email_login_attempts"
        ),
    )
    op.create_index(
        "ix_email_login_user_created",
        "email_login_challenges",
        ["user_id", "created_at"],
    )
    op.add_column(
        "account_emails",
        sa.Column(
            "login_challenge_id",
            UUID(),
            sa.ForeignKey("email_login_challenges.id", ondelete="SET NULL"),
        ),
    )
    op.execute("ALTER TABLE email_login_challenges ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE email_login_challenges FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY email_login_owner ON email_login_challenges USING (
      current_setting('app.guest_mode',true) IS DISTINCT FROM 'true' AND
      (current_setting('app.is_super_admin',true)='true' OR user_id::text=current_setting('app.current_user_id',true)))
      WITH CHECK (current_setting('app.guest_mode',true) IS DISTINCT FROM 'true' AND
      (current_setting('app.is_super_admin',true)='true' OR user_id::text=current_setting('app.current_user_id',true)))"""
    )
    op.execute(
        """CREATE POLICY audit_account_email_login_insert ON audit_logs FOR INSERT WITH CHECK (
      lodge_id IS NULL AND actor_user_id::text=current_setting('app.current_user_id',true)
      AND resource_type='account' AND resource_id=actor_user_id::text AND action='auth.email_otp.verified')"""
    )
    # Existing non-platform sessions must not retain the superseded factor policy.
    # Platform enrolments and sessions are deliberately preserved.
    op.execute(
        "UPDATE auth_sessions SET revoked_at=now() WHERE revoked_at IS NULL AND user_id IN (SELECT id FROM users WHERE NOT is_super_admin)"
    )
    op.execute(
        "UPDATE users SET mfa_secret_encrypted=NULL,mfa_enabled_at=NULL,mfa_last_timestep=NULL,mfa_recovery_hashes='[]'::jsonb WHERE NOT is_super_admin"
    )


def downgrade():
    op.execute("DROP POLICY audit_account_email_login_insert ON audit_logs")
    op.drop_column("account_emails", "login_challenge_id")
    op.drop_table("email_login_challenges")
    # Erased enrolment secrets and revoked sessions cannot be reconstructed.
