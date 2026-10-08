"""durable operation proposals"""
from alembic import op
import sqlalchemy as sa

revision = "20261007_03"
down_revision = "20261007_02"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("operation_proposals", sa.Column("id", sa.String(80), primary_key=True), sa.Column("trip_id", sa.String(80), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False), sa.Column("base_version", sa.Integer(), nullable=False), sa.Column("owner_id", sa.String(255), nullable=False), sa.Column("idempotency_key", sa.String(255), nullable=False), sa.Column("request_fingerprint", sa.String(64), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("preview", sa.JSON(), nullable=False), sa.Column("committed_version", sa.Integer(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("trip_id", "owner_id", "idempotency_key", name="uq_operation_proposals_trip_owner_key"))
    op.create_index("ix_operation_proposals_trip_id", "operation_proposals", ["trip_id"])

def downgrade():
    op.drop_index("ix_operation_proposals_trip_id", table_name="operation_proposals")
    op.drop_table("operation_proposals")
