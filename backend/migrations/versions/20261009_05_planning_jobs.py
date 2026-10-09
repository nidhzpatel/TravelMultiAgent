"""Add durable planning jobs and progress events."""

from alembic import op
import sqlalchemy as sa

revision = "20261009_05"
down_revision = "20261009_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planning_jobs",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("trip_id", sa.String(80), sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(255), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("checkpoint", sa.JSON(), nullable=False),
        sa.Column("result_version", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(120), nullable=True),
        sa.Column("token_budget", sa.Integer(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("cost_budget_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("cost_used_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trip_id", "owner_id", "idempotency_key", name="uq_planning_jobs_trip_owner_key"),
    )
    op.create_index("ix_planning_jobs_trip_id", "planning_jobs", ["trip_id"])
    op.create_index("ix_planning_jobs_owner_id", "planning_jobs", ["owner_id"])
    op.create_index("ix_planning_jobs_status", "planning_jobs", ["status"])
    op.create_table(
        "planning_job_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(80), sa.ForeignKey("planning_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "sequence", name="uq_planning_job_events_sequence"),
    )
    op.create_index("ix_planning_job_events_job_id", "planning_job_events", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_planning_job_events_job_id", table_name="planning_job_events")
    op.drop_table("planning_job_events")
    op.drop_index("ix_planning_jobs_status", table_name="planning_jobs")
    op.drop_index("ix_planning_jobs_owner_id", table_name="planning_jobs")
    op.drop_index("ix_planning_jobs_trip_id", table_name="planning_jobs")
    op.drop_table("planning_jobs")
