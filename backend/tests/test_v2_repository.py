from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.domain.contracts import Budget, Money, PriceStatus, Provenance, Trip, TripBrief
from app.persistence.repositories import SqlAlchemyTripRepository


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


if __name__ == "__main__":
    unittest.main()
