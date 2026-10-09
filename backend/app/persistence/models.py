from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TripRecord(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class TripVersionRecord(Base):
    __tablename__ = "trip_versions"
    __table_args__ = (UniqueConstraint("trip_id", "version", name="uq_trip_versions_trip_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class TripMemberRecord(Base):
    __tablename__ = "trip_members"
    __table_args__ = (UniqueConstraint("trip_id", "user_id", name="uq_trip_members_trip_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("owner_id", "key", name="uq_idempotency_owner_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_payload: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class RateLimitRecord(Base):
    __tablename__ = "rate_limit_records"
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProposalRecord(Base):
    __tablename__ = "operation_proposals"
    __table_args__ = (UniqueConstraint("trip_id", "owner_id", "idempotency_key", name="uq_operation_proposals_trip_owner_key"),)
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    preview: Mapped[dict] = mapped_column(JSON, nullable=False)
    committed_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ProviderItemRecord(Base):
    __tablename__ = "provider_items"
    __table_args__ = (
        UniqueConstraint("trip_id", "trip_version", "kind", "provider", "provider_item_id", name="uq_provider_items_identity"),
    )

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    trip_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_item_id: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class ProviderRunRecord(Base):
    __tablename__ = "provider_runs"
    __table_args__ = (
        UniqueConstraint("trip_id", "trip_version", "kind", "provider", name="uq_provider_runs_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    trip_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class PlanningJobRecord(Base):
    __tablename__ = "planning_jobs"
    __table_args__ = (UniqueConstraint("trip_id", "owner_id", "idempotency_key", name="uq_planning_jobs_trip_owner_key"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    checkpoint: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    token_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_budget_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    cost_used_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class PlanningJobEventRecord(Base):
    __tablename__ = "planning_job_events"
    __table_args__ = (UniqueConstraint("job_id", "sequence", name="uq_planning_job_events_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("planning_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
