from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from datetime import timedelta
from typing import Iterator, Protocol

from sqlalchemy import Engine, Select, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts import Trip, TripVersion
from app.persistence.models import Base, IdempotencyRecord, ProposalRecord, RateLimitRecord, TripMemberRecord, TripRecord, TripVersionRecord, utcnow


class VersionConflictError(Exception):
    pass


class QuotaExceededError(Exception):
    pass


class TripRepository(Protocol):
    def create(self, trip: Trip, idempotency_key: str | None = None) -> TripVersion: ...
    def get(self, trip_id: str) -> TripVersion | None: ...
    def get_version(self, trip_id: str, version: int) -> TripVersion | None: ...
    def list_for_owner(self, owner_id: str) -> list[TripVersion]: ...
    def append_version(self, trip: Trip, expected_version: int) -> TripVersion: ...
    def member_role(self, trip_id: str, user_id: str) -> str | None: ...
    def set_member_role(self, trip_id: str, user_id: str, role: str) -> None: ...


class SqlAlchemyTripRepository:
    """Transactional persistence for immutable snapshots.

    This repository intentionally exposes no arbitrary JSON write method. Future
    operations construct validated domain models before appending a version.
    """

    def __init__(self, database_url: str, *, engine: Engine | None = None) -> None:
        if engine is not None:
            self.engine = engine
        elif database_url == "sqlite:///:memory:":
            self.engine = create_engine(database_url, future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool)
        else:
            self.engine = create_engine(database_url, future=True, pool_pre_ping=True)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def create_schema_for_test(self) -> None:
        """Test-only helper; deployed environments run Alembic migrations."""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def _session(self) -> Iterator[Session]:
        with self._sessions.begin() as session:
            yield session

    def create(self, trip: Trip, idempotency_key: str | None = None) -> TripVersion:
        snapshot = TripVersion(trip_id=trip.id, version=1, trip=trip)
        payload = snapshot.model_dump(mode="json")
        # The response snapshot has a generated creation timestamp. Fingerprint the
        # validated request instead so a genuine retry retains its idempotency key.
        fingerprint = self._fingerprint(trip.model_dump(mode="json"))
        with self._session() as session:
            if idempotency_key:
                previous = session.scalar(
                    select(IdempotencyRecord).where(
                        IdempotencyRecord.owner_id == trip.owner_id,
                        IdempotencyRecord.key == idempotency_key,
                    )
                )
                if previous:
                    if previous.request_fingerprint != fingerprint:
                        raise ValueError("Idempotency key was reused for a different request")
                    return TripVersion.model_validate_json(previous.response_payload)
            session.add(TripRecord(id=trip.id, owner_id=trip.owner_id, title=trip.title, current_version=1))
            session.add(TripMemberRecord(trip_id=trip.id, user_id=trip.owner_id, role="OWNER"))
            session.add(TripVersionRecord(trip_id=trip.id, version=1, snapshot=payload))
            if idempotency_key:
                session.add(
                    IdempotencyRecord(
                        owner_id=trip.owner_id,
                        key=idempotency_key,
                        request_fingerprint=fingerprint,
                        response_payload=snapshot.model_dump_json(),
                    )
                )
        return snapshot

    def get(self, trip_id: str) -> TripVersion | None:
        with self._session() as session:
            row = session.execute(
                select(TripVersionRecord.snapshot)
                .join(TripRecord, TripRecord.id == TripVersionRecord.trip_id)
                .where(TripVersionRecord.trip_id == trip_id, TripVersionRecord.version == TripRecord.current_version)
            ).scalar_one_or_none()
        return TripVersion.model_validate(row) if row else None

    def append_version(self, trip: Trip, expected_version: int) -> TripVersion:
        """Append a validated snapshot only when the caller has the current version."""
        with self._session() as session:
            record = session.scalar(select(TripRecord).where(TripRecord.id == trip.id).with_for_update())
            if record is None:
                raise KeyError("Trip not found")
            if record.current_version != expected_version:
                raise VersionConflictError("Trip changed; fetch the latest version before retrying")
            next_version = expected_version + 1
            snapshot = TripVersion(trip_id=trip.id, version=next_version, trip=trip)
            session.add(TripVersionRecord(trip_id=trip.id, version=next_version, snapshot=snapshot.model_dump(mode="json")))
            record.title = trip.title
            record.current_version = next_version
        return snapshot

    def get_version(self, trip_id: str, version: int) -> TripVersion | None:
        with self._session() as session:
            row = session.scalar(
                select(TripVersionRecord.snapshot).where(
                    TripVersionRecord.trip_id == trip_id, TripVersionRecord.version == version
                )
            )
        return TripVersion.model_validate(row) if row else None

    def list_for_owner(self, owner_id: str) -> list[TripVersion]:
        statement: Select[tuple[dict]] = (
            select(TripVersionRecord.snapshot)
            .join(TripRecord, TripRecord.id == TripVersionRecord.trip_id)
            .where(TripRecord.owner_id == owner_id, TripVersionRecord.version == TripRecord.current_version)
            .order_by(TripRecord.updated_at.desc())
        )
        with self._session() as session:
            rows = session.scalars(statement).all()
        return [TripVersion.model_validate(row) for row in rows]

    def member_role(self, trip_id: str, user_id: str) -> str | None:
        with self._session() as session:
            return session.scalar(
                select(TripMemberRecord.role).where(
                    TripMemberRecord.trip_id == trip_id,
                    TripMemberRecord.user_id == user_id,
                )
            )

    def consume_quota(self, key: str, limit: int, window_seconds: int = 60) -> None:
        with self._session() as session:
            record = session.scalar(select(RateLimitRecord).where(RateLimitRecord.key == key).with_for_update())
            if record is None:
                session.add(RateLimitRecord(key=key, count=1))
            elif (record.window_started_at.replace(tzinfo=utcnow().tzinfo) if record.window_started_at.tzinfo is None else record.window_started_at) + timedelta(seconds=window_seconds) <= utcnow():
                record.window_started_at = utcnow()
                record.count = 1
            elif record.count >= limit:
                raise QuotaExceededError("Rate limit exceeded")
            else:
                record.count += 1

    def set_member_role(self, trip_id: str, user_id: str, role: str) -> None:
        if role not in {"OWNER", "EDITOR", "VIEWER"}:
            raise ValueError("Unsupported membership role")
        with self._session() as session:
            record = session.scalar(
                select(TripMemberRecord).where(
                    TripMemberRecord.trip_id == trip_id,
                    TripMemberRecord.user_id == user_id,
                )
            )
            if record:
                record.role = role
            else:
                session.add(TripMemberRecord(trip_id=trip_id, user_id=user_id, role=role))

    def create_proposal(self, proposal_id: str, trip_id: str, owner_id: str, idempotency_key: str, base_version: int, payload: dict, preview: dict, idempotency_payload: dict | None = None) -> str:
        fingerprint = self._fingerprint(idempotency_payload if idempotency_payload is not None else payload)
        with self._session() as session:
            existing = session.scalar(select(ProposalRecord).where(ProposalRecord.trip_id == trip_id, ProposalRecord.owner_id == owner_id, ProposalRecord.idempotency_key == idempotency_key))
            if existing:
                if existing.request_fingerprint != fingerprint:
                    raise ValueError("Idempotency key was reused for a different proposal")
                return existing.id
            try:
                with session.begin_nested():
                    session.add(ProposalRecord(id=proposal_id, trip_id=trip_id, owner_id=owner_id, idempotency_key=idempotency_key, request_fingerprint=fingerprint, base_version=base_version, payload=payload, preview=preview))
                    session.flush()
            except IntegrityError:
                existing = session.scalar(select(ProposalRecord).where(ProposalRecord.trip_id == trip_id, ProposalRecord.owner_id == owner_id, ProposalRecord.idempotency_key == idempotency_key))
                if existing is None:
                    raise
                if existing.request_fingerprint != fingerprint:
                    raise ValueError("Idempotency key was reused for a different proposal")
                return existing.id
        return proposal_id

    def get_proposal_by_key(self, trip_id: str, owner_id: str, idempotency_key: str, payload: dict) -> ProposalRecord | None:
        fingerprint = self._fingerprint(payload)
        with self._session() as session:
            proposal = session.scalar(select(ProposalRecord).where(ProposalRecord.trip_id == trip_id, ProposalRecord.owner_id == owner_id, ProposalRecord.idempotency_key == idempotency_key))
            if proposal and proposal.request_fingerprint != fingerprint:
                raise ValueError("Idempotency key was reused for a different proposal")
            return proposal

    def get_proposal(self, proposal_id: str, trip_id: str, owner_id: str) -> ProposalRecord | None:
        with self._session() as session:
            return session.scalar(select(ProposalRecord).where(ProposalRecord.id == proposal_id, ProposalRecord.trip_id == trip_id, ProposalRecord.owner_id == owner_id))

    def mark_proposal_committed(self, proposal_id: str, version: int) -> None:
        with self._session() as session:
            proposal = session.get(ProposalRecord, proposal_id)
            if proposal is None:
                raise KeyError("Proposal not found")
            proposal.committed_version = version

    @staticmethod
    def _fingerprint(payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
