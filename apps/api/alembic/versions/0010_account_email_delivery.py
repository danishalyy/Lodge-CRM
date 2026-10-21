"""Durable encrypted account email delivery, platform invitations, and worker leases."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = '0010_account_email_delivery'
down_revision = '0009_lodge_branding'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('email_notifications_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('users', sa.Column('email_min_severity', sa.String(20), nullable=False, server_default='normal'))
    op.alter_column('invitations', 'lodge_id', nullable=True)
    op.drop_constraint('ck_notification_delivery_status','notification_deliveries',type_='check')
    op.create_check_constraint('ck_notification_delivery_status','notification_deliveries',"status in ('pending','sending','sent','failed','dead','cancelled')")
    op.add_column('notification_deliveries', sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table('account_emails',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('lodge_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('lodges.id', ondelete='CASCADE'), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('invitation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('invitations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('reset_token_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('password_reset_tokens.id', ondelete='CASCADE'), nullable=True),
        sa.Column('kind', sa.String(30), nullable=False), sa.Column('destination', sa.String(320), nullable=False),
        sa.Column('encrypted_payload', sa.Text(), nullable=True), sa.Column('status', sa.String(20), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False), sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True), sa.Column('last_error', sa.Text(), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    for col in ['lodge_id', 'user_id']:
        op.create_index('ix_account_emails_'+col, 'account_emails', [col])
    op.create_index('ix_account_emails_due', 'account_emails', ['status', 'next_attempt_at'])
    op.execute('ALTER TABLE account_emails ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE account_emails FORCE ROW LEVEL SECURITY')
    op.execute("""CREATE POLICY account_emails_scope ON account_emails USING (
        current_setting('app.is_super_admin', true)='true' OR lodge_id::text=current_setting('app.current_lodge_id', true)
    ) WITH CHECK (current_setting('app.is_super_admin', true)='true' OR lodge_id::text=current_setting('app.current_lodge_id', true))""")

def downgrade():
    op.drop_table('account_emails')
    op.drop_column('users', 'email_notifications_enabled')
    op.drop_column('users', 'email_min_severity')
    op.drop_column('notification_deliveries', 'lease_expires_at')
    op.execute("UPDATE notification_deliveries SET status='dead' WHERE status='cancelled'")
    op.drop_constraint('ck_notification_delivery_status','notification_deliveries',type_='check')
    op.create_check_constraint('ck_notification_delivery_status','notification_deliveries',"status in ('pending','sending','sent','failed','dead')")
    # Platform invitations cannot be represented by the previous mandatory lodge column.
    op.execute('DELETE FROM invitations WHERE lodge_id IS NULL')
    op.alter_column('invitations', 'lodge_id', nullable=False)
