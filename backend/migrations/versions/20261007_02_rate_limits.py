"""durable rate limits"""
from alembic import op
import sqlalchemy as sa
revision = "20261007_02"
down_revision = "20260928_01"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("rate_limit_records", sa.Column("key", sa.String(255), primary_key=True), sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("count", sa.Integer(), nullable=False))
def downgrade():
    op.drop_table("rate_limit_records")
