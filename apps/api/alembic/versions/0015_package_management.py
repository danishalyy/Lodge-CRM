"""Editable package metadata, optimistic revision and explained lodge exceptions."""
from alembic import op
import sqlalchemy as sa
revision='0015_package_management'
down_revision='0014_administrator_delegation'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('plans',sa.Column('description',sa.Text(),nullable=False,server_default=''))
    op.add_column('plans',sa.Column('revision',sa.Integer(),nullable=False,server_default='1'))
    op.add_column('plans',sa.Column('sort_order',sa.Integer(),nullable=False,server_default='0'))
    op.add_column('lodge_entitlement_overrides',sa.Column('reason',sa.String(1000),nullable=False,server_default=''))
    PLAN_DESCRIPTIONS={'Basic': 'Run the lodge day to day: guests, rooms, stays, requests, staff, tasks, housekeeping, maintenance, activities, vehicles and reports.', 'Standard': 'Expanded lodge operations, departments, custom roles, guest feedback, staff records and rosters, food and drink, fuel, transfers, wildlife and ranger tools, with offline wildlife recording where enabled.', 'Premium': 'Expanded operational access. Automation, AI summaries, live tracking and external system connections are coming soon and are not included as working capabilities.'}
    for index,(key,description) in enumerate(PLAN_DESCRIPTIONS.items()):
        op.execute(sa.text('UPDATE plans SET description=:description,sort_order=:sort WHERE key=:key').bindparams(description=description,sort=index,key=key))

def downgrade():
    op.drop_column('lodge_entitlement_overrides','reason')
    for column in ['sort_order','revision','description']:op.drop_column('plans',column)
