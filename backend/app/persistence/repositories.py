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
from app.persistence.models import Base, IdempotencyRecord, ProposalRecord, ProviderItemRecord, ProviderRunRecord, RateLimitRecord, TripMemberRecord, TripRecord, TripShareRecord, TripVersionRecord, utcnow
from app.providers.alternatives import NormalizedProviderItem, ProviderItemKind, ProviderRun


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

    def list_members(self, trip_id: str) -> tuple[tuple[str, str], ...]:
        with self._session() as session:
            rows = session.execute(
                select(TripMemberRecord.user_id, TripMemberRecord.role)
                .where(TripMemberRecord.trip_id == trip_id)
                .order_by(TripMemberRecord.created_at, TripMemberRecord.user_id)
            ).all()
        return tuple((user_id, role) for user_id, role in rows)

    def remove_member(self, trip_id: str, user_id: str) -> bool:
        with self._session() as session:
            record = session.scalar(select(TripMemberRecord).where(TripMemberRecord.trip_id == trip_id, TripMemberRecord.user_id == user_id).with_for_update())
            if record is None:
                return False
            if record.role == "OWNER":
                raise ValueError("The trip owner cannot be removed")
            session.delete(record)
            return True

    def create_share(self, record: TripShareRecord) -> None:
        with self._session() as session:
            session.add(record)

    def list_shares(self, trip_id: str) -> tuple[TripShareRecord, ...]:
        with self._session() as session:
            return tuple(session.scalars(select(TripShareRecord).where(TripShareRecord.trip_id == trip_id).order_by(TripShareRecord.created_at.desc())).all())

    def get_share(self, share_id: str) -> TripShareRecord | None:
        with self._session() as session:
            return session.get(TripShareRecord, share_id)

    def revoke_share(self, share_id: str) -> TripShareRecord | None:
        with self._session() as session:
            record = session.scalar(select(TripShareRecord).where(TripShareRecord.id == share_id).with_for_update())
            if record is None:
                return None
            if record.revoked_at is None:
                record.revoked_at = utcnow()
                if record.accepted_by:
                    member = session.scalar(select(TripMemberRecord).where(TripMemberRecord.trip_id == record.trip_id, TripMemberRecord.user_id == record.accepted_by).with_for_update())
                    if member is not None and member.role != "OWNER":
                        session.delete(member)
            session.flush()
            return record

    def accept_share(self, token_hash: str, user_id: str) -> tuple[str, str]:
        with self._session() as session:
            share = session.scalar(select(TripShareRecord).where(TripShareRecord.token_hash == token_hash).with_for_update())
            if share is None:
                raise KeyError("Share invitation not found")
            expires_at = share.expires_at if share.expires_at.tzinfo else share.expires_at.replace(tzinfo=utcnow().tzinfo)
            if share.revoked_at is not None or expires_at <= utcnow():
                raise ValueError("Share invitation is no longer active")
            if share.accepted_by not in {None, user_id}:
                raise ValueError("Share invitation was already accepted")
            member = session.scalar(select(TripMemberRecord).where(TripMemberRecord.trip_id == share.trip_id, TripMemberRecord.user_id == user_id).with_for_update())
            if member is None:
                session.add(TripMemberRecord(trip_id=share.trip_id, user_id=user_id, role=share.role))
            elif member.role != "OWNER":
                member.role = share.role
            share.accepted_by = user_id
            share.accepted_at = share.accepted_at or utcnow()
            return share.trip_id, share.role

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

    def replace_provider_items(
        self,
        trip_id: str,
        trip_version: int,
        kind: ProviderItemKind,
        provider: str,
        items: tuple[NormalizedProviderItem, ...],
    ) -> None:
        if any(
            item.trip_id != trip_id
            or item.trip_version != trip_version
            or item.kind != kind
            or item.provider != provider
            for item in items
        ):
            raise ValueError("Provider item scope does not match the replacement scope")
        with self._session() as session:
            current = session.scalars(
                select(ProviderItemRecord).where(
                    ProviderItemRecord.trip_id == trip_id,
                    ProviderItemRecord.trip_version == trip_version,
                    ProviderItemRecord.kind == kind.value,
                )
            ).all()
            for record in current:
                session.delete(record)
            for item in items:
                session.add(
                    ProviderItemRecord(
                        id=item.id,
                        trip_id=trip_id,
                        trip_version=trip_version,
                        kind=kind.value,
                        provider=provider,
                        provider_item_id=item.provider_item_id,
                        payload=item.model_dump(mode="json"),
                        expires_at=item.expires_at,
                    )
                )

    def list_provider_items(self, trip_id: str, trip_version: int) -> tuple[NormalizedProviderItem, ...]:
        with self._session() as session:
            payloads = session.scalars(
                select(ProviderItemRecord.payload)
                .where(
                    ProviderItemRecord.trip_id == trip_id,
                    ProviderItemRecord.trip_version == trip_version,
                )
                .order_by(ProviderItemRecord.kind, ProviderItemRecord.provider, ProviderItemRecord.provider_item_id)
            ).all()
        return tuple(NormalizedProviderItem.model_validate(payload) for payload in payloads)

    def save_provider_run(self, run: ProviderRun) -> None:
        with self._session() as session:
            obsolete = session.scalars(
                select(ProviderRunRecord).where(
                    ProviderRunRecord.trip_id == run.trip_id,
                    ProviderRunRecord.trip_version == run.trip_version,
                    ProviderRunRecord.kind == run.kind.value,
                    ProviderRunRecord.provider != run.provider,
                )
            ).all()
            for item in obsolete:
                session.delete(item)
            record = session.scalar(
                select(ProviderRunRecord).where(
                    ProviderRunRecord.trip_id == run.trip_id,
                    ProviderRunRecord.trip_version == run.trip_version,
                    ProviderRunRecord.kind == run.kind.value,
                    ProviderRunRecord.provider == run.provider,
                )
            )
            payload = run.model_dump(mode="json")
            if record:
                record.payload = payload
            else:
                session.add(ProviderRunRecord(trip_id=run.trip_id, trip_version=run.trip_version, kind=run.kind.value, provider=run.provider, payload=payload))

    def list_provider_runs(self, trip_id: str, trip_version: int) -> tuple[ProviderRun, ...]:
        with self._session() as session:
            payloads = session.scalars(
                select(ProviderRunRecord.payload)
                .where(ProviderRunRecord.trip_id == trip_id, ProviderRunRecord.trip_version == trip_version)
                .order_by(ProviderRunRecord.kind, ProviderRunRecord.provider)
            ).all()
        return tuple(ProviderRun.model_validate(payload) for payload in payloads)

    @staticmethod
    def _fingerprint(payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
