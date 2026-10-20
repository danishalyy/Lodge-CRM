"""Super Admin managed lodge branding, with normalized private logo assets."""
from alembic import op
import sqlalchemy as sa
revision='0009_lodge_branding'
down_revision='0008_security_integrity'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('lodges',sa.Column('brand_name',sa.String(180),nullable=False,server_default=''))
    op.add_column('lodges',sa.Column('logo_png',sa.LargeBinary(),nullable=True))

def downgrade():
    op.drop_column('lodges','logo_png')
    op.drop_column('lodges','brand_name')
