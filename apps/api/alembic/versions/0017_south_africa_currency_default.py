"""Default new lodges to South African rand, preserving existing choices."""
from alembic import op
import sqlalchemy as sa
revision='0017_south_africa_currency'
down_revision='0016_default_lodge_currency'
branch_labels=None
depends_on=None

def upgrade():
    op.alter_column('lodges','currency',existing_type=sa.String(3),server_default='ZAR',existing_nullable=False)

def downgrade():
    op.alter_column('lodges','currency',existing_type=sa.String(3),server_default='PKR',existing_nullable=False)
