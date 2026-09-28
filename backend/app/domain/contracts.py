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


class Fact(DomainModel):
    value: str | int | Decimal | bool | None = None
    status: FactStatus
    evidence_ids: tuple[OpaqueId, ...] = ()
    valid_at: datetime | None = None


class Money(DomainModel):
    # Currency-specific rounding is applied by pricing policy, not by storage.
    amount: Decimal
    currency: CurrencyCode
    status: PriceStatus
    provenance: Provenance
    evidence_ids: tuple[OpaqueId, ...] = ()

    @field_validator("amount")
    @classmethod
    def reject_non_finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("Money amount must be finite")
        return value


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


class Expense(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("expense"))
    category: Literal["flight", "hotel", "transport", "food", "activity", "tax", "contingency"]
    money: Money
    quantity: Decimal = Decimal("1")
    included: bool = False


class Budget(DomainModel):
    id: OpaqueId = Field(default_factory=lambda: new_id("budget"))
    target: Money
    expense_ids: tuple[OpaqueId, ...] = ()


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
