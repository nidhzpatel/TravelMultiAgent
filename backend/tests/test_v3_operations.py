import unittest
from pydantic import ValidationError
from app.operations.contracts import Operation, OperationKind, ProposalRequest
from app.operations.service import apply_operations
from app.domain.contracts import Budget, Money, PriceStatus, Provenance, Trip, TripBrief
from decimal import Decimal


class OperationContractTests(unittest.TestCase):
    def test_rejects_arbitrary_operation_shape(self) -> None:
        with self.assertRaises(ValidationError):
            ProposalRequest(expected_version=1, idempotency_key="x" * 16, operations=[{"kind": "REPLACE", "unknown": True}])

    def test_typed_replace_operation(self) -> None:
        operation = Operation(kind=OperationKind.REPLACE, path="title", value="Revised trip")
        self.assertEqual(operation.kind, OperationKind.REPLACE)

    def test_replace_is_scoped_and_deterministic(self) -> None:
        trip = Trip(owner_id="user", title="Original", brief=TripBrief(destination_text="Goa"), budget=Budget(target=Money(amount=Decimal("1"), currency="USD", status=PriceStatus.USER_PROVIDED, provenance=Provenance.USER)))
        proposal = ProposalRequest(expected_version=1, idempotency_key="x" * 16, operations=[Operation(kind=OperationKind.REPLACE, path="title", value="Revised")])
        self.assertEqual(apply_operations(trip, proposal).title, "Revised")


if __name__ == "__main__":
    unittest.main()
