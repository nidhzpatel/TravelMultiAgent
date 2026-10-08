from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from pydantic import ValidationError

from app.domain.contracts import (
    Budget,
    BudgetFeasibility,
    Evidence,
    Expense,
    Fact,
    FactStatus,
    FxSnapshot,
    Money,
    PriceStatus,
    ProviderOutcomeStatus,
    Provenance,
    Trip,
    TripBrief,
    TripReadiness,
)
from app.evidence.service import normalize_fact, normalize_money
from app.planning.budget import build_budget_breakdown
from app.providers.base import ProviderResult


class BudgetEngineTests(unittest.TestCase):
    def money(self, amount: str | None, currency: str = "INR", status: PriceStatus = PriceStatus.ESTIMATED, provenance: Provenance = Provenance.LIVE, evidence_ids: tuple[str, ...] = ()) -> Money:
        return Money(amount=Decimal(amount) if amount is not None else None, currency=currency, status=status, provenance=provenance, evidence_ids=evidence_ids)

    def target(self, amount: str = "5000") -> Money:
        return self.money(amount, status=PriceStatus.USER_PROVIDED, provenance=Provenance.USER)

    def test_unknown_cost_has_no_fabricated_zero_and_blocks_feasibility(self) -> None:
        unknown = Expense(category="hotel", money=self.money(None, status=PriceStatus.UNKNOWN), mandatory=True)
        result = build_budget_breakdown(Budget(target=self.target(), expenses=(unknown,)))
        self.assertEqual(result.known_total, Decimal("0.00"))
        self.assertEqual(result.feasibility, BudgetFeasibility.UNKNOWN)
        self.assertEqual(result.mandatory_unknown_expense_ids, (unknown.id,))
        with self.assertRaises(ValidationError):
            self.money("0", status=PriceStatus.UNKNOWN)

    def test_native_currency_fx_rounding_taxes_and_no_budget_scaling(self) -> None:
        fx = FxSnapshot(base_currency="USD", quote_currency="INR", rate=Decimal("80"))
        expense = Expense(category="flight", money=self.money("10.005", "USD"), quantity=Decimal("1"), taxes=(self.money("1.001", "USD"),), fx_snapshot=fx)
        contingency = Expense(category="contingency", money=self.money("100"))
        result = build_budget_breakdown(Budget(target=self.target("500"), expenses=(expense, contingency)))
        self.assertEqual(result.estimated_subtotal, Decimal("900.40"))
        self.assertEqual(result.taxes_total, Decimal("80.08"))
        self.assertEqual(result.contingency_total, Decimal("100.00"))
        self.assertEqual(result.known_total, Decimal("980.48"))
        self.assertEqual(result.shortfall, Decimal("480.48"))

    def test_duplicate_and_included_expenses_are_not_double_counted(self) -> None:
        expense = Expense(category="transport", money=self.money("100"))
        with self.assertRaises(ValidationError):
            Budget(target=self.target(), expenses=(expense, expense))
        included = Expense(category="tax", money=self.money("50"), included=True)
        result = build_budget_breakdown(Budget(target=self.target(), expenses=(expense, included)))
        self.assertEqual(result.known_total, Decimal("100.00"))

    def test_stale_evidence_downgrades_verified_fact_and_price(self) -> None:
        now = datetime.now(timezone.utc)
        evidence = Evidence(source="provider", retrieved_at=now - timedelta(hours=2), expires_at=now - timedelta(hours=1), covered_fields=("price",), provenance=Provenance.LIVE)
        fact = Fact(value=True, status=FactStatus.VERIFIED, evidence_ids=(evidence.id,))
        price = self.money("100", status=PriceStatus.VERIFIED, evidence_ids=(evidence.id,))
        self.assertEqual(normalize_fact(fact, (evidence,), now).status, FactStatus.STALE)
        self.assertEqual(normalize_money(price, (evidence,), now).status, PriceStatus.ESTIMATED)
        expense = Expense(category="flight", money=price)
        breakdown = build_budget_breakdown(Budget(target=self.target(), expenses=(expense,), evidence=(evidence,)))
        self.assertEqual(breakdown.verified_subtotal, Decimal("0.00"))
        self.assertEqual(breakdown.estimated_subtotal, Decimal("100.00"))

    def test_mock_cannot_be_verified_or_ready_to_book(self) -> None:
        with self.assertRaises(ValidationError):
            self.money("100", status=PriceStatus.VERIFIED, provenance=Provenance.MOCK, evidence_ids=("evidence_" + "a" * 32,))
        mock = Expense(category="hotel", money=self.money("100", provenance=Provenance.MOCK))
        breakdown = build_budget_breakdown(Budget(target=self.target(), expenses=(mock,)))
        self.assertEqual(breakdown.verified_subtotal, Decimal("0.00"))
        with self.assertRaises(ValidationError):
            Trip(owner_id="user", title="Trip", brief=TripBrief(destination_text="Goa"), budget=Budget(target=self.target(), expenses=(mock,)), readiness=TripReadiness.READY_TO_BOOK)
        with self.assertRaises(ValidationError):
            Evidence(source="mock", provenance=Provenance.MOCK, provider_outcome=ProviderOutcomeStatus.SUCCESS)

    def test_provider_outcomes_do_not_smuggle_values_or_hide_errors(self) -> None:
        self.assertEqual(ProviderResult[str](status=ProviderOutcomeStatus.SUCCESS, value="offer").value, "offer")
        with self.assertRaises(ValidationError):
            ProviderResult[str](status=ProviderOutcomeStatus.SUCCESS)
        with self.assertRaises(ValidationError):
            ProviderResult[str](status=ProviderOutcomeStatus.ERROR, value="fabricated", error_code="timeout")
        with self.assertRaises(ValidationError):
            ProviderResult[str](status=ProviderOutcomeStatus.ERROR)


if __name__ == "__main__":
    unittest.main()
