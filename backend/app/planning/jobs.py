"""Typed durable planning-job contracts."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.contracts import OpaqueId, Trip, new_id


class PlanningJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRY_WAIT = "RETRY_WAIT"
    NEEDS_INPUT = "NEEDS_INPUT"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

    @property
    def terminal(self) -> bool:
        return self in {self.NEEDS_INPUT, self.SUCCEEDED, self.FAILED, self.CANCELLED, self.EXPIRED}


class PlanningJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    idempotency_key: str = Field(min_length=16, max_length=255)
    deadline_seconds: int = Field(default=300, ge=5, le=1800)
    max_attempts: int = Field(default=3, ge=1, le=5)
    token_budget: int = Field(default=12000, ge=100, le=100000)
    cost_budget_usd: Decimal = Field(default=Decimal("2.00"), ge=0, le=100)


class PlanningJob(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: OpaqueId = Field(default_factory=lambda: new_id("job"))
    trip_id: OpaqueId
    owner_id: str = Field(min_length=1, max_length=255)
    base_version: int = Field(ge=1)
    status: PlanningJobStatus = PlanningJobStatus.QUEUED
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(ge=1, le=5)
    fencing_token: int = Field(default=0, ge=0)
    lease_owner: str | None = Field(default=None, max_length=255)
    lease_expires_at: datetime | None = None
    next_attempt_at: datetime | None = None
    deadline_at: datetime
    cancel_requested: bool = False
    checkpoint: dict[str, object] = Field(default_factory=dict)
    result_version: int | None = Field(default=None, ge=1)
    error_code: str | None = Field(default=None, max_length=120)
    token_budget: int = Field(ge=100)
    tokens_used: int = Field(default=0, ge=0)
    cost_budget_usd: Decimal = Field(ge=0)
    cost_used_usd: Decimal = Field(default=Decimal("0"), ge=0)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_job_times(self) -> "PlanningJob":
        timestamps = [self.deadline_at, self.created_at, self.updated_at]
        timestamps.extend(item for item in (self.lease_expires_at, self.next_attempt_at) if item)
        if any(item.tzinfo is None for item in timestamps):
            raise ValueError("Planning job timestamps must be timezone-aware")
        if self.deadline_at <= self.created_at:
            raise ValueError("Planning job deadline must follow creation")
        if self.status is PlanningJobStatus.SUCCEEDED and self.result_version is None:
            raise ValueError("Successful planning jobs require a result version")
        return self


class PlanningJobEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: OpaqueId
    sequence: int = Field(ge=1)
    event_type: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=500)
    progress_percent: int = Field(ge=0, le=100)
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class PlanningCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trip: Trip
    advisory_notes: tuple[str, ...] = ()
