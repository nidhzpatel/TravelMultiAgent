from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from typing import Iterator, Protocol

from sqlalchemy import Engine, Select, create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.domain.contracts import Trip, TripVersion
from app.persistence.models import Base, IdempotencyRecord, TripMemberRecord, TripRecord, TripVersionRecord


class VersionConflictError(Exception):
    pass


class TripRepository(Protocol):
    def create(self, trip: Trip, idempotency_key: str | None = None) -> TripVersion: ...
    def get(self, trip_id: str) -> TripVersion | None: ...
    def get_version(self, trip_id: str, version: int) -> TripVersion | None: ...
    def list_for_owner(self, owner_id: str) -> list[TripVersion]: ...
    def append_version(self, trip: Trip, expected_version: int) -> TripVersion: ...


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

    @staticmethod
    def _fingerprint(payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
