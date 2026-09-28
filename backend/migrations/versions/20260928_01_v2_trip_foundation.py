"""v2 trip persistence foundation.

Revision ID: 20260928_01
Revises:
Create Date: 2026-09-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20260928_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trips",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("owner_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trips_owner_id", "trips", ["owner_id"])
    op.create_table(
        "trip_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trip_id", sa.String(length=80), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trip_id", "version", name="uq_trip_versions_trip_version"),
    )
    op.create_index("ix_trip_versions_trip_id", "trip_versions", ["trip_id"])
    op.create_table(
        "trip_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trip_id", sa.String(length=80), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trip_id", "user_id", name="uq_trip_members_trip_user"),
    )
    op.create_index("ix_trip_members_trip_id", "trip_members", ["trip_id"])
    op.create_index("ix_trip_members_user_id", "trip_members", ["user_id"])
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.String(length=255), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response_payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "key", name="uq_idempotency_owner_key"),
    )
    op.create_index("ix_idempotency_records_owner_id", "idempotency_records", ["owner_id"])


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("trip_members")
    op.drop_table("trip_versions")
    op.drop_table("trips")
