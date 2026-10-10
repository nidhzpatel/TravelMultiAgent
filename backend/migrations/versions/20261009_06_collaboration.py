"""Add revocable trip share invitations."""

from alembic import op
import sqlalchemy as sa

revision = "20261009_06"
down_revision = "20261009_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trip_shares",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("trip_id", sa.String(80), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by", sa.String(255), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trip_shares_trip_id", "trip_shares", ["trip_id"])
    op.create_index("ix_trip_shares_created_by", "trip_shares", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_trip_shares_created_by", table_name="trip_shares")
    op.drop_index("ix_trip_shares_trip_id", table_name="trip_shares")
    op.drop_table("trip_shares")
