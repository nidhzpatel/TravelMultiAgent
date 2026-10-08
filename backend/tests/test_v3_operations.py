import unittest
from pydantic import ValidationError
from app.operations.contracts import Operation, OperationKind, ProposalRequest
from app.operations.service import apply_operations, changed_fields
from app.operations.intent import resolve_message
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
        self.assertEqual(changed_fields(trip, apply_operations(trip, proposal)), ("title",))

    def test_interest_operations_and_scoped_replan(self) -> None:
        trip = Trip(owner_id="user", title="Trip", brief=TripBrief(destination_text="Goa"), budget=Budget(target=Money(amount=Decimal("1"), currency="USD", status=PriceStatus.USER_PROVIDED, provenance=Provenance.USER)))
        def apply(kind, **values):
            return apply_operations(trip, ProposalRequest(expected_version=1, idempotency_key="y" * 16, operations=[Operation(kind=kind, path="preferences.interests", **values)]))
        self.assertEqual(apply(OperationKind.ADD, value="food").preferences.interests, ("food",))
        trip = apply(OperationKind.ADD, value="food").model_copy(update={"preferences": apply(OperationKind.ADD, value="food").preferences.model_copy(update={"interests": ("food", "beaches")})})
        self.assertEqual(apply_operations(trip, ProposalRequest(expected_version=1, idempotency_key="z" * 16, operations=[Operation(kind=OperationKind.REMOVE, path="preferences.interests", value="food")])).preferences.interests, ("beaches",))
        paced = apply_operations(trip, ProposalRequest(expected_version=1, idempotency_key="p" * 16, operations=[Operation(kind=OperationKind.REPLAN, path="preferences.pace", value="slow")]))
        self.assertEqual(paced.preferences.pace, "slow")
        moved = apply_operations(trip, ProposalRequest(expected_version=1, idempotency_key="m" * 16, operations=[Operation(kind=OperationKind.MOVE, path="preferences.interests", value="beaches", index=0)]))
        self.assertEqual(moved.preferences.interests, ("beaches", "food"))
        reordered = apply_operations(trip, ProposalRequest(expected_version=1, idempotency_key="r" * 16, operations=[Operation(kind=OperationKind.REORDER, path="preferences.interests", values=("beaches", "food"))]))
        self.assertEqual(reordered.preferences.interests, ("beaches", "food"))
        self.assertEqual(changed_fields(trip, paced), ("preferences.pace",))

    def test_read_and_failed_patch_preserve_original_and_stable_ids(self) -> None:
        day_id = "day_" + "a" * 32
        trip = Trip(owner_id="user", title="Trip", brief=TripBrief(destination_text="Goa"), budget=Budget(target=Money(amount=Decimal("1"), currency="USD", status=PriceStatus.USER_PROVIDED, provenance=Provenance.USER)), day_ids=(day_id,))
        read = ProposalRequest(expected_version=1, idempotency_key="q" * 16, operations=[Operation(kind=OperationKind.READ, path="title")])
        self.assertEqual(apply_operations(trip, read), trip)
        changed = apply_operations(trip, ProposalRequest(expected_version=1, idempotency_key="a" * 16, operations=[Operation(kind=OperationKind.ADD, path="preferences.interests", value="food")]))
        self.assertEqual(changed.day_ids, (day_id,))
        self.assertEqual(changed_fields(trip, changed), ("preferences.interests",))
        with self.assertRaises(ValidationError):
            Operation(kind=OperationKind.REPLAN, path="preferences.pace", value="reckless")
        self.assertEqual(trip.preferences.pace, "balanced")

    def test_intent_resolution_returns_proposal_or_ambiguity(self) -> None:
        resolved = resolve_message("rename trip to Coastal escape", 1, "i" * 16)
        self.assertEqual(resolved.proposal.operations[0].value, "Coastal escape")
        self.assertIn("alternative", resolve_message("change my second hotel", 1, "j" * 16).question)
        self.assertIsNotNone(resolve_message("When is my flight?", 1, "k" * 16).answer)
        self.assertEqual(resolve_message("set pace to slow", 1, "l" * 16).proposal.operations[0].kind, OperationKind.REPLAN)


if __name__ == "__main__":
    unittest.main()
