"""Immutable, transport-safe contracts for the production v2 trip model."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def new_id(prefix: str) -> str:
    """Return an opaque, stable ID. Array positions are never identifiers."""
    return f"{prefix}_{uuid4().hex}"


OpaqueId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9]*_[0-9a-f]{32}$")]
CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class FactStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"


class PriceStatus(StrEnum):
    VERIFIED = "VERIFIED"
    ESTIMATED = "ESTIMATED"
    USER_PROVIDED = "USER_PROVIDED"
    UNKNOWN = "UNKNOWN"


class Provenance(StrEnum):
    LIVE = "LIVE"
    MOCK = "MOCK"
    USER = "USER"
    LEGACY = "LEGACY"


class ProviderOutcomeStatus(StrEnum):
    SUCCESS = "SUCCESS"
    NO_RESULTS = "NO_RESULTS"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"
    MOCK = "MOCK"


class TripReadiness(StrEnum):
    DRAFT = "DRAFT"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    READY_TO_BOOK = "READY_TO_BOOK"


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Evidence(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("evidence"))
    source: str = Field(min_length=1, max_length=120)
    reference_url: str | None = Field(default=None, max_length=2048)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    covered_fields: tuple[str, ...] = ()
    provenance: Provenance
    provider_outcome: ProviderOutcomeStatus = ProviderOutcomeStatus.SUCCESS
    retention_permitted: bool = True
    retention_until: datetime | None = None

    @model_validator(mode="after")
    def check_retention(self) -> "Evidence":
        if not self.retention_permitted and self.retention_until is not None:
            raise ValueError("Non-retainable evidence cannot have a retention deadline")
        if self.retention_until and self.retention_until < self.retrieved_at:
            raise ValueError("Evidence retention cannot end before retrieval")
        if self.provider_outcome is ProviderOutcomeStatus.MOCK and self.provenance is not Provenance.MOCK:
            raise ValueError("Mock provider outcomes require mock provenance")
        if self.provenance is Provenance.MOCK and self.provider_outcome is not ProviderOutcomeStatus.MOCK:
            raise ValueError("Mock provenance requires an explicit mock provider outcome")
        return self


class Fact(DomainModel):
    value: str | int | Decimal | bool | None = None
    status: FactStatus
    evidence_ids: tuple[OpaqueId, ...] = ()
    valid_at: datetime | None = None


class Money(DomainModel):
    # Currency-specific rounding is applied by pricing policy, not by storage.
    amount: Decimal | None
    currency: CurrencyCode
    status: PriceStatus
    provenance: Provenance
    evidence_ids: tuple[OpaqueId, ...] = ()

    @field_validator("amount")
    @classmethod
    def reject_non_finite(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if not value.is_finite():
            raise ValueError("Money amount must be finite")
        if value < 0:
            raise ValueError("Money amount must be nonnegative")
        return value

    @model_validator(mode="after")
    def unknowns_are_not_zero(self) -> "Money":
        if self.status is PriceStatus.UNKNOWN and self.amount is not None:
            raise ValueError("Unknown money must not carry a fabricated amount")
        if self.status is not PriceStatus.UNKNOWN and self.amount is None:
            raise ValueError("Known money requires an amount")
        if self.status is PriceStatus.VERIFIED and self.provenance is not Provenance.LIVE:
            raise ValueError("Only live provider money can be verified")
        if self.status is PriceStatus.VERIFIED and not self.evidence_ids:
            raise ValueError("Verified money requires field evidence")
        return self


class TripBrief(DomainModel):
    origin: str | None = Field(default=None, max_length=200)
    destination_text: str = Field(min_length=2, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    travelers: int = Field(default=1, ge=1, le=20)

    @model_validator(mode="after")
    def check_date_range(self) -> "TripBrief":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self


class TravelerPreferences(DomainModel):
    interests: tuple[str, ...] = ()
    pace: Literal["slow", "balanced", "fast"] = "balanced"
    dietary_requirements: tuple[str, ...] = ()
    mobility_requirements: tuple[str, ...] = ()
    lodging_preferences: tuple[str, ...] = ()
    transport_preferences: tuple[str, ...] = ()


class Destination(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("destination"))
    name: str = Field(min_length=2, max_length=200)
    provider_place_id: str | None = Field(default=None, max_length=300)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(default=None, max_length=80)
    evidence_ids: tuple[OpaqueId, ...] = ()


class ScheduledItem(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("item"))
    kind: Literal["activity", "restaurant", "flight", "hotel", "transport"]
    entity_id: OpaqueId
    start_at: datetime | None = None
    end_at: datetime | None = None

    @model_validator(mode="after")
    def check_time_window(self) -> "ScheduledItem":
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValueError("Scheduled item ends before it starts")
        return self


class TripDay(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("day"))
    local_date: date
    timezone: str = Field(min_length=1, max_length=80)
    scheduled_item_ids: tuple[OpaqueId, ...] = ()


class Activity(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("activity"))
    place_id: str | None = None
    name: str = Field(min_length=1, max_length=300)
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    opening_hours: Fact = Field(default_factory=lambda: Fact(status=FactStatus.UNKNOWN))
    expense_ids: tuple[OpaqueId, ...] = ()


class Restaurant(Activity):
    cuisine: tuple[str, ...] = ()
    dietary_support: Fact = Field(default_factory=lambda: Fact(status=FactStatus.UNKNOWN))


class Flight(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("flight"))
    provider_offer_id: str | None = None
    price: Money
    availability: Fact = Field(default_factory=lambda: Fact(status=FactStatus.UNKNOWN))
    evidence_ids: tuple[OpaqueId, ...] = ()


class Hotel(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("hotel"))
    provider_offer_id: str | None = None
    price: Money
    meal_inclusions: Fact = Field(default_factory=lambda: Fact(status=FactStatus.UNKNOWN))
    evidence_ids: tuple[OpaqueId, ...] = ()


class TransportLeg(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("transport"))
    origin_destination_id: OpaqueId
    destination_destination_id: OpaqueId
    mode: Literal["flight", "train", "bus", "metro", "cab", "walk"]
    duration_minutes: Fact = Field(default_factory=lambda: Fact(status=FactStatus.UNKNOWN))
    expense_ids: tuple[OpaqueId, ...] = ()


class FxSnapshot(DomainModel):
    base_currency: CurrencyCode
    quote_currency: CurrencyCode
    rate: Decimal = Field(gt=0)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evidence_id: OpaqueId | None = None


class Expense(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("expense"))
    category: Literal["flight", "hotel", "transport", "food", "activity", "tax", "contingency"]
    money: Money
    unit: Literal["item", "person", "night", "room", "leg", "trip"] = "item"
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    taxes: tuple[Money, ...] = ()
    taxes_included: bool = False
    exclusions: tuple[str, ...] = ()
    included: bool = False
    mandatory: bool = True
    fx_snapshot: FxSnapshot | None = None

    @model_validator(mode="after")
    def validate_currency_scope(self) -> "Expense":
        if any(tax.currency != self.money.currency for tax in self.taxes):
            raise ValueError("Expense taxes must use the native expense currency")
        return self
class BudgetFeasibility(StrEnum):
    WITHIN_BUDGET = "WITHIN_BUDGET"
    OVER_BUDGET = "OVER_BUDGET"
    UNKNOWN = "UNKNOWN"


class BudgetBreakdown(DomainModel):
    currency: CurrencyCode
    verified_subtotal: Decimal
    estimated_subtotal: Decimal
    user_provided_subtotal: Decimal
    taxes_total: Decimal
    contingency_total: Decimal
    known_total: Decimal
    unknown_expense_ids: tuple[OpaqueId, ...] = ()
    mandatory_unknown_expense_ids: tuple[OpaqueId, ...] = ()
    feasibility: BudgetFeasibility
    shortfall: Decimal | None = None


class Budget(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("budget"))
    target: Money
    expense_ids: tuple[OpaqueId, ...] = ()
    expenses: tuple[Expense, ...] = ()
    evidence: tuple[Evidence, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def populate_expense_ids(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("expenses"):
            value = dict(value)
            expenses: list[Expense | dict] = []
            for item in value["expenses"]:
                if isinstance(item, Expense):
                    expenses.append(item)
                else:
                    expense = dict(item)
                    expense.setdefault("id", new_id("expense"))
                    expenses.append(expense)
            value["expenses"] = tuple(expenses)
            if not value.get("expense_ids"):
                value["expense_ids"] = tuple(item.id if isinstance(item, Expense) else item["id"] for item in expenses)
        return value

    @model_validator(mode="after")
    def reconcile_references(self) -> "Budget":
        ids = tuple(expense.id for expense in self.expenses)
        if len(ids) != len(set(ids)):
            raise ValueError("Budget contains duplicate expenses")
        if self.expense_ids and self.expense_ids != ids:
            raise ValueError("Budget expense_ids must match ordered expenses")
        return self


class Alternative(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("alternative"))
    target_entity_id: OpaqueId
    label: str = Field(min_length=1, max_length=300)
    evidence_ids: tuple[OpaqueId, ...] = ()


class AlternativeSet(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("alternatives"))
    source_version: int = Field(ge=1)
    target_entity_id: OpaqueId
    alternative_ids: tuple[OpaqueId, ...]
    expires_at: datetime | None = None


class ValidationResult(DomainModel):
    rule: str = Field(min_length=1, max_length=120)
    severity: Literal["info", "warning", "error"]
    message: str = Field(min_length=1, max_length=1000)
    entity_ids: tuple[OpaqueId, ...] = ()


class OperationProposal(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("proposal"))
    trip_id: OpaqueId
    base_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=16, max_length=255)
    operations: tuple[dict[str, object], ...]
    validation_results: tuple[ValidationResult, ...] = ()


class Trip(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("trip"))
    owner_id: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=200)
    brief: TripBrief
    preferences: TravelerPreferences = Field(default_factory=TravelerPreferences)
    budget: Budget
    destination_ids: tuple[OpaqueId, ...] = ()
    day_ids: tuple[OpaqueId, ...] = ()
    readiness: TripReadiness = TripReadiness.DRAFT

    @model_validator(mode="after")
    def ready_trip_has_complete_budget(self) -> "Trip":
        if self.readiness is TripReadiness.READY_TO_BOOK:
            if any(
                expense.mandatory
                and (
                    expense.money.status is PriceStatus.UNKNOWN
                    or any(tax.status is PriceStatus.UNKNOWN for tax in expense.taxes)
                    or (expense.money.currency != self.budget.target.currency and expense.fx_snapshot is None)
                )
                for expense in self.budget.expenses
            ):
                raise ValueError("A mandatory unknown cost blocks READY_TO_BOOK")
            if any(
                expense.money.provenance is Provenance.MOCK
                or any(tax.provenance is Provenance.MOCK for tax in expense.taxes)
                for expense in self.budget.expenses
            ):
                raise ValueError("Mock costs cannot produce READY_TO_BOOK")
        return self


class TripVersion(DomainModel):
    trip_id: OpaqueId
    version: int = Field(ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trip: Trip
    validation_results: tuple[ValidationResult, ...] = ()

    @model_validator(mode="after")
    def version_matches_trip(self) -> "TripVersion":
        if self.trip.id != self.trip_id:
            raise ValueError("TripVersion trip_id must match the nested trip")
        return self
