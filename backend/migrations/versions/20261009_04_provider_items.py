"""Persist normalized provider items."""

from alembic import op
import sqlalchemy as sa

revision = "20261009_04"
down_revision = "20261007_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_items",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("trip_id", sa.String(80), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trip_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("provider_item_id", sa.String(500), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trip_id", "trip_version", "kind", "provider", "provider_item_id", name="uq_provider_items_identity"),
    )
    op.create_index("ix_provider_items_trip_id", "provider_items", ["trip_id"])
    op.create_table(
        "provider_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trip_id", sa.String(80), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trip_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trip_id", "trip_version", "kind", "provider", name="uq_provider_runs_scope"),
    )
    op.create_index("ix_provider_runs_trip_id", "provider_runs", ["trip_id"])


def downgrade() -> None:
    op.drop_index("ix_provider_runs_trip_id", table_name="provider_runs")
    op.drop_table("provider_runs")
    op.drop_index("ix_provider_items_trip_id", table_name="provider_items")
    op.drop_table("provider_items")
