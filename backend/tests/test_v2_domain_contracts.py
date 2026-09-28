from decimal import Decimal
import unittest

from pydantic import ValidationError

from app.domain.contracts import (
    Budget,
    FactStatus,
    Money,
    PriceStatus,
    Provenance,
    Trip,
    TripBrief,
    TripVersion,
)


class V2DomainContractTests(unittest.TestCase):
    def _budget(self) -> Budget:
        return Budget(
            target=Money(
                amount=Decimal("1000"),
                currency="USD",
                status=PriceStatus.USER_PROVIDED,
                provenance=Provenance.USER,
            )
        )

    def test_money_uses_decimal_and_serializes_without_float_loss(self) -> None:
        money = Money(
            amount=Decimal("10.129"),
            currency="INR",
            status=PriceStatus.ESTIMATED,
            provenance=Provenance.LIVE,
        )
        self.assertEqual(money.amount, Decimal("10.129"))
        self.assertEqual(money.model_dump(mode="json")["amount"], "10.129")

    def test_trip_version_preserves_stable_trip_id(self) -> None:
        trip = Trip(
            owner_id="user_123",
            title="Goa",
            brief=TripBrief(destination_text="Goa"),
            budget=self._budget(),
        )
        version = TripVersion(trip_id=trip.id, version=1, trip=trip)
        self.assertEqual(version.trip_id, trip.id)
        self.assertTrue(trip.id.startswith("trip_"))

    def test_unknown_fact_is_explicit(self) -> None:
        self.assertEqual(FactStatus.UNKNOWN.value, "UNKNOWN")

    def test_arbitrary_fields_and_non_finite_money_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Money(
                amount=Decimal("NaN"),
                currency="USD",
                status=PriceStatus.ESTIMATED,
                provenance=Provenance.MOCK,
            )
        with self.assertRaises(ValidationError):
            TripBrief(destination_text="Goa", unexpected="no")


if __name__ == "__main__":
    unittest.main()
