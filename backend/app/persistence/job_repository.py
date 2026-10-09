"""Transactional durable queue with leases and fencing-token commit safety."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterator

from sqlalchemy import Engine, and_, create_engine, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.contracts import Trip, TripVersion, new_id
from app.persistence.models import PlanningJobEventRecord, PlanningJobRecord, TripRecord, TripVersionRecord
from app.planning.jobs import PlanningCandidate, PlanningJob, PlanningJobEvent, PlanningJobRequest, PlanningJobStatus


class StaleFenceError(Exception):
    pass


class JobCancelledError(Exception):
    pass


class JobDeadlineError(Exception):
    pass


class JobBudgetError(Exception):
    pass


class JobBaseVersionError(Exception):
    pass


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


class SqlAlchemyPlanningJobRepository:
    def __init__(self, database_url: str, *, engine: Engine | None = None) -> None:
        if engine is not None:
            self.engine = engine
        elif database_url == "sqlite:///:memory:":
            self.engine = create_engine(database_url, future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        else:
            self.engine = create_engine(database_url, future=True, pool_pre_ping=True)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def _session(self) -> Iterator[Session]:
        with self._sessions.begin() as session:
            yield session

    @staticmethod
    def _fingerprint(base_version: int, request: PlanningJobRequest) -> str:
        payload = {"base_version": base_version, **request.model_dump(mode="json")}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _event(session: Session, job: PlanningJobRecord, event_type: str, message: str, progress: int, payload: dict | None = None) -> None:
        sequence = (session.scalar(select(func.max(PlanningJobEventRecord.sequence)).where(PlanningJobEventRecord.job_id == job.id)) or 0) + 1
        session.add(PlanningJobEventRecord(job_id=job.id, sequence=sequence, event_type=event_type, message=message, progress_percent=progress, payload=payload or {}, created_at=datetime.now(timezone.utc)))

    @staticmethod
    def _to_job(row: PlanningJobRecord) -> PlanningJob:
        return PlanningJob(
            id=row.id,
            trip_id=row.trip_id,
            owner_id=row.owner_id,
            base_version=row.base_version,
            status=PlanningJobStatus(row.status),
            attempt_count=row.attempt_count,
            max_attempts=row.max_attempts,
            fencing_token=row.fencing_token,
            lease_owner=row.lease_owner,
            lease_expires_at=_aware(row.lease_expires_at),
            next_attempt_at=_aware(row.next_attempt_at),
            deadline_at=_aware(row.deadline_at),
            cancel_requested=row.cancel_requested,
            checkpoint=row.checkpoint or {},
            result_version=row.result_version,
            error_code=row.error_code,
            token_budget=row.token_budget,
            tokens_used=row.tokens_used,
            cost_budget_usd=row.cost_budget_usd,
            cost_used_usd=row.cost_used_usd,
            created_at=_aware(row.created_at),
            updated_at=_aware(row.updated_at),
        )

    def create(self, trip_id: str, owner_id: str, base_version: int, request: PlanningJobRequest, now: datetime | None = None) -> PlanningJob:
        now = now or datetime.now(timezone.utc)
        fingerprint = self._fingerprint(base_version, request)
        with self._session() as session:
            existing = session.scalar(select(PlanningJobRecord).where(PlanningJobRecord.trip_id == trip_id, PlanningJobRecord.owner_id == owner_id, PlanningJobRecord.idempotency_key == request.idempotency_key))
            if existing:
                if existing.request_fingerprint != fingerprint:
                    raise ValueError("Idempotency key was reused for a different planning request")
                return self._to_job(existing)
            row = PlanningJobRecord(
                id=new_id("job"), trip_id=trip_id, owner_id=owner_id, idempotency_key=request.idempotency_key,
                request_fingerprint=fingerprint, base_version=base_version, status=PlanningJobStatus.QUEUED.value,
                attempt_count=0, max_attempts=request.max_attempts, fencing_token=0,
                deadline_at=now + timedelta(seconds=request.deadline_seconds), checkpoint={},
                token_budget=request.token_budget, tokens_used=0, cost_budget_usd=request.cost_budget_usd,
                cost_used_usd=Decimal("0"), created_at=now, updated_at=now,
            )
            try:
                with session.begin_nested():
                    session.add(row)
                    session.flush()
            except IntegrityError:
                existing = session.scalar(select(PlanningJobRecord).where(PlanningJobRecord.trip_id == trip_id, PlanningJobRecord.owner_id == owner_id, PlanningJobRecord.idempotency_key == request.idempotency_key))
                if existing is None:
                    raise
                if existing.request_fingerprint != fingerprint:
                    raise ValueError("Idempotency key was reused for a different planning request")
                return self._to_job(existing)
            self._event(session, row, "queued", "Planning job queued", 0)
            return self._to_job(row)

    def get(self, job_id: str) -> PlanningJob | None:
        with self._session() as session:
            row = session.get(PlanningJobRecord, job_id)
            return self._to_job(row) if row else None

    def list_for_trip(self, trip_id: str) -> tuple[PlanningJob, ...]:
        with self._session() as session:
            rows = session.scalars(select(PlanningJobRecord).where(PlanningJobRecord.trip_id == trip_id).order_by(PlanningJobRecord.created_at.desc())).all()
            return tuple(self._to_job(row) for row in rows)

    def events(self, job_id: str, after_sequence: int = 0) -> tuple[PlanningJobEvent, ...]:
        with self._session() as session:
            rows = session.scalars(select(PlanningJobEventRecord).where(PlanningJobEventRecord.job_id == job_id, PlanningJobEventRecord.sequence > after_sequence).order_by(PlanningJobEventRecord.sequence)).all()
        return tuple(PlanningJobEvent(job_id=row.job_id, sequence=row.sequence, event_type=row.event_type, message=row.message, progress_percent=row.progress_percent, payload=row.payload or {}, created_at=_aware(row.created_at)) for row in rows)

    def claim_next(self, worker_id: str, lease_seconds: int = 30, now: datetime | None = None) -> PlanningJob | None:
        now = now or datetime.now(timezone.utc)
        with self._session() as session:
            while True:
                row = session.scalar(
                    select(PlanningJobRecord).where(
                        or_(
                            PlanningJobRecord.status == PlanningJobStatus.QUEUED.value,
                            and_(PlanningJobRecord.status == PlanningJobStatus.RETRY_WAIT.value, or_(PlanningJobRecord.next_attempt_at.is_(None), PlanningJobRecord.next_attempt_at <= now)),
                            and_(PlanningJobRecord.status == PlanningJobStatus.RUNNING.value, PlanningJobRecord.lease_expires_at <= now),
                        )
                    ).order_by(PlanningJobRecord.created_at, PlanningJobRecord.id).limit(1).with_for_update(skip_locked=True)
                )
                if row is None:
                    return None
                if _aware(row.deadline_at) <= now:
                    row.status = PlanningJobStatus.EXPIRED.value
                    row.error_code = "queue_deadline_exceeded"
                    row.updated_at = now
                    self._event(session, row, "expired", "Planning deadline expired before execution", 100)
                    session.flush()
                    continue
                if row.cancel_requested:
                    row.status = PlanningJobStatus.CANCELLED.value
                    row.updated_at = now
                    self._event(session, row, "cancelled", "Planning job cancelled", 100)
                    session.flush()
                    continue
                if row.attempt_count >= row.max_attempts:
                    row.status = PlanningJobStatus.FAILED.value
                    row.error_code = "retry_budget_exhausted"
                    row.updated_at = now
                    self._event(session, row, "failed", "Planning retry budget exhausted", 100)
                    session.flush()
                    continue
                reclaimed = row.status == PlanningJobStatus.RUNNING.value
                row.status = PlanningJobStatus.RUNNING.value
                row.attempt_count += 1
                row.fencing_token += 1
                row.lease_owner = worker_id
                row.lease_expires_at = now + timedelta(seconds=lease_seconds)
                row.next_attempt_at = None
                row.updated_at = now
                self._event(session, row, "reclaimed" if reclaimed else "started", "Planning lease claimed", 5, {"attempt": row.attempt_count})
                session.flush()
                return self._to_job(row)

    def _leased(self, session: Session, job_id: str, worker_id: str, fencing_token: int, now: datetime) -> PlanningJobRecord:
        row = session.scalar(select(PlanningJobRecord).where(PlanningJobRecord.id == job_id).with_for_update())
        if row is None:
            raise KeyError("Planning job not found")
        if row.status != PlanningJobStatus.RUNNING.value or row.lease_owner != worker_id or row.fencing_token != fencing_token:
            raise StaleFenceError("Planning lease is stale")
        if _aware(row.lease_expires_at) <= now:
            raise StaleFenceError("Planning lease expired")
        if row.cancel_requested:
            raise JobCancelledError("Planning job was cancelled")
        if _aware(row.deadline_at) <= now:
            raise JobDeadlineError("Planning job deadline expired")
        return row

    def heartbeat(self, job_id: str, worker_id: str, fencing_token: int, lease_seconds: int = 30, now: datetime | None = None) -> PlanningJob:
        now = now or datetime.now(timezone.utc)
        with self._session() as session:
            row = self._leased(session, job_id, worker_id, fencing_token, now)
            row.lease_expires_at = now + timedelta(seconds=lease_seconds)
            row.updated_at = now
            return self._to_job(row)

    def checkpoint(self, job_id: str, worker_id: str, fencing_token: int, step: str, progress: int, payload: dict | None = None, now: datetime | None = None) -> PlanningJob:
        now = now or datetime.now(timezone.utc)
        with self._session() as session:
            row = self._leased(session, job_id, worker_id, fencing_token, now)
            row.checkpoint = {"step": step, **(payload or {})}
            row.updated_at = now
            self._event(session, row, "progress", step, progress, payload)
            return self._to_job(row)

    def record_usage(self, job_id: str, worker_id: str, fencing_token: int, tokens: int, cost_usd: Decimal, now: datetime | None = None) -> PlanningJob:
        now = now or datetime.now(timezone.utc)
        with self._session() as session:
            row = self._leased(session, job_id, worker_id, fencing_token, now)
            if row.tokens_used + tokens > row.token_budget or row.cost_used_usd + cost_usd > row.cost_budget_usd:
                raise JobBudgetError("Planning model budget exceeded")
            row.tokens_used += tokens
            row.cost_used_usd += cost_usd
            row.updated_at = now
            return self._to_job(row)

    def request_cancel(self, job_id: str, now: datetime | None = None) -> PlanningJob:
        now = now or datetime.now(timezone.utc)
        with self._session() as session:
            row = session.scalar(select(PlanningJobRecord).where(PlanningJobRecord.id == job_id).with_for_update())
            if row is None:
                raise KeyError("Planning job not found")
            if PlanningJobStatus(row.status).terminal:
                return self._to_job(row)
            row.cancel_requested = True
            row.updated_at = now
            if row.status in {PlanningJobStatus.QUEUED.value, PlanningJobStatus.RETRY_WAIT.value}:
                row.status = PlanningJobStatus.CANCELLED.value
                self._event(session, row, "cancelled", "Planning job cancelled", 100)
            else:
                self._event(session, row, "cancellation_requested", "Cancellation requested", 95)
            return self._to_job(row)

    def retry(self, job_id: str, worker_id: str, fencing_token: int, error_code: str, delay_seconds: int, now: datetime | None = None) -> PlanningJob:
        now = now or datetime.now(timezone.utc)
        with self._session() as session:
            row = self._leased(session, job_id, worker_id, fencing_token, now)
            row.lease_owner = None
            row.lease_expires_at = None
            row.error_code = error_code
            row.updated_at = now
            if row.attempt_count >= row.max_attempts or now + timedelta(seconds=delay_seconds) >= _aware(row.deadline_at):
                row.status = PlanningJobStatus.FAILED.value
                self._event(session, row, "failed", "Planning retry budget exhausted", 100, {"error_code": error_code})
            else:
                row.status = PlanningJobStatus.RETRY_WAIT.value
                row.next_attempt_at = now + timedelta(seconds=delay_seconds)
                self._event(session, row, "retry_scheduled", "Planning retry scheduled", 10, {"error_code": error_code})
            return self._to_job(row)

    def finish_without_commit(self, job_id: str, worker_id: str, fencing_token: int, status: PlanningJobStatus, error_code: str, message: str, now: datetime | None = None) -> PlanningJob:
        if status not in {PlanningJobStatus.NEEDS_INPUT, PlanningJobStatus.FAILED, PlanningJobStatus.CANCELLED, PlanningJobStatus.EXPIRED}:
            raise ValueError("Unsupported terminal status")
        now = now or datetime.now(timezone.utc)
        with self._session() as session:
            row = self._leased(session, job_id, worker_id, fencing_token, now)
            row.status = status.value
            row.error_code = error_code
            row.lease_owner = None
            row.lease_expires_at = None
            row.updated_at = now
            self._event(session, row, status.value.lower(), message, 100, {"error_code": error_code})
            return self._to_job(row)

    def acknowledge_cancellation(self, job_id: str, worker_id: str, fencing_token: int, now: datetime | None = None) -> PlanningJob:
        now = now or datetime.now(timezone.utc)
        with self._session() as session:
            row = session.scalar(select(PlanningJobRecord).where(PlanningJobRecord.id == job_id).with_for_update())
            if row is None:
                raise KeyError("Planning job not found")
            if row.status != PlanningJobStatus.RUNNING.value or row.lease_owner != worker_id or row.fencing_token != fencing_token:
                raise StaleFenceError("Planning lease is stale")
            row.status = PlanningJobStatus.CANCELLED.value
            row.cancel_requested = True
            row.lease_owner = None
            row.lease_expires_at = None
            row.updated_at = now
            self._event(session, row, "cancelled", "Planning job cancelled", 100)
            return self._to_job(row)

    def acknowledge_deadline(self, job_id: str, worker_id: str, fencing_token: int, now: datetime | None = None) -> PlanningJob:
        now = now or datetime.now(timezone.utc)
        with self._session() as session:
            row = session.scalar(select(PlanningJobRecord).where(PlanningJobRecord.id == job_id).with_for_update())
            if row is None:
                raise KeyError("Planning job not found")
            if row.status != PlanningJobStatus.RUNNING.value or row.lease_owner != worker_id or row.fencing_token != fencing_token:
                raise StaleFenceError("Planning lease is stale")
            row.status = PlanningJobStatus.EXPIRED.value
            row.error_code = "planning_deadline_exceeded"
            row.lease_owner = None
            row.lease_expires_at = None
            row.updated_at = now
            self._event(session, row, "expired", "Planning deadline expired", 100)
            return self._to_job(row)

    def commit_candidate(self, job_id: str, worker_id: str, fencing_token: int, candidate: PlanningCandidate, now: datetime | None = None) -> PlanningJob:
        now = now or datetime.now(timezone.utc)
        with self._session() as session:
            row = self._leased(session, job_id, worker_id, fencing_token, now)
            trip_record = session.scalar(select(TripRecord).where(TripRecord.id == row.trip_id).with_for_update())
            if trip_record is None:
                raise KeyError("Trip not found")
            if trip_record.current_version != row.base_version:
                raise JobBaseVersionError("Trip changed after planning started")
            candidate_trip = Trip.model_validate(candidate.trip)
            if candidate_trip.id != row.trip_id or candidate_trip.owner_id != trip_record.owner_id:
                raise ValueError("Planning candidate changed immutable trip identity")
            next_version = row.base_version + 1
            version = TripVersion(trip_id=row.trip_id, version=next_version, trip=candidate_trip)
            session.add(TripVersionRecord(trip_id=row.trip_id, version=next_version, snapshot=version.model_dump(mode="json"), created_at=now))
            trip_record.current_version = next_version
            trip_record.title = candidate_trip.title
            row.status = PlanningJobStatus.SUCCEEDED.value
            row.result_version = next_version
            row.lease_owner = None
            row.lease_expires_at = None
            row.updated_at = now
            self._event(session, row, "succeeded", "Accepted planning draft committed", 100, {"version": next_version, "advisory_notes": list(candidate.advisory_notes)})
            return self._to_job(row)
