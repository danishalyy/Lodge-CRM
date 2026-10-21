"""Store only hashed one-time MFA recovery codes on their owning account."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = '0012_mfa_recovery_codes'
down_revision = '0011_lodge_groups'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('mfa_recovery_hashes', JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    # Account-security events may be appended only for the authenticated owner.
    # This grants no read, update, delete, or cross-account audit access.
    op.execute("""CREATE POLICY audit_account_mfa_insert ON audit_logs FOR INSERT WITH CHECK (
      lodge_id IS NULL AND actor_user_id::text=current_setting('app.current_user_id',true)
      AND resource_type='account' AND resource_id=current_setting('app.current_user_id',true)
      AND action IN ('mfa.enabled','mfa.disabled','mfa.verified','mfa.recovery_used','mfa.recovery_regenerated'))""")

def downgrade():
    op.execute("DROP POLICY IF EXISTS audit_account_mfa_insert ON audit_logs")
    op.drop_column('users', 'mfa_recovery_hashes')
