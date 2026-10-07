from decimal import Decimal
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.domain.contracts import Budget, Money, PriceStatus, Provenance, Trip, TripBrief
from app.persistence.repositories import QuotaExceededError, SqlAlchemyTripRepository, VersionConflictError
from app.persistence.models import RateLimitRecord, utcnow


class V2RepositoryTests(unittest.TestCase):
    def _trip(self) -> Trip:
        return Trip(
            owner_id="user_alice",
            title="Goa itinerary",
            brief=TripBrief(destination_text="Goa"),
            budget=Budget(
                target=Money(
                    amount=Decimal("800.00"),
                    currency="USD",
                    status=PriceStatus.USER_PROVIDED,
                    provenance=Provenance.USER,
                )
            ),
        )

    def test_snapshot_survives_repository_restart(self) -> None:
        with TemporaryDirectory() as directory:
            url = f"sqlite:///{Path(directory) / 'trips.db'}"
            first = SqlAlchemyTripRepository(url)
            first.create_schema_for_test()
            trip = self._trip()
            created = first.create(trip, idempotency_key="create-goa-trip-0001")

            restarted = SqlAlchemyTripRepository(url)
            restored = restarted.get(trip.id)
            self.assertEqual(restored, created)
            self.assertEqual(restarted.get_version(trip.id, 1), created)

    def test_create_is_idempotent_and_owner_scoped(self) -> None:
        repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        repository.create_schema_for_test()
        trip = self._trip()
        created = repository.create(trip, idempotency_key="create-goa-trip-0002")
        retried = repository.create(trip, idempotency_key="create-goa-trip-0002")
        self.assertEqual(created, retried)
        self.assertEqual(repository.list_for_owner("user_alice"), [created])
        self.assertEqual(repository.list_for_owner("user_bob"), [])

    def test_append_creates_immutable_next_version_and_rejects_stale_write(self) -> None:
        repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        repository.create_schema_for_test()
        original = self._trip()
        repository.create(original)
        renamed = original.model_copy(update={"title": "Goa, revised"})
        second = repository.append_version(renamed, expected_version=1)
        self.assertEqual(second.version, 2)
        self.assertEqual(repository.get_version(original.id, 1).trip.title, "Goa itinerary")
        self.assertEqual(repository.get(original.id).trip.title, "Goa, revised")
        with self.assertRaises(VersionConflictError):
            repository.append_version(renamed, expected_version=1)

    def test_durable_quota_rejects_excess_requests(self) -> None:
        repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        repository.create_schema_for_test()
        repository.consume_quota("user_alice", 2)
        repository.consume_quota("user_alice", 2)
        with self.assertRaises(QuotaExceededError):
            repository.consume_quota("user_alice", 2)
        with repository._session() as session:
            session.get(RateLimitRecord, "user_alice").window_started_at = utcnow() - timedelta(seconds=61)
        repository.consume_quota("user_alice", 2, window_seconds=60)


if __name__ == "__main__":
    unittest.main()
