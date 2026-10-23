"""Use PKR for newly created lodges; preserve every existing lodge currency."""
from alembic import op
import sqlalchemy as sa
revision='0016_default_lodge_currency'
down_revision='0015_package_management'
branch_labels=None
depends_on=None

def upgrade():
    op.alter_column('lodges','currency',existing_type=sa.String(3),server_default='PKR',existing_nullable=False)

def downgrade():
    op.alter_column('lodges','currency',existing_type=sa.String(3),server_default='ZAR',existing_nullable=False)
