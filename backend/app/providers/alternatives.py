"""Normalized, persistent provider results consumed by planning and the UI."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.contracts import Evidence, Fact, Money, OpaqueId, ProviderOutcomeStatus, new_id


class ProviderItemKind(StrEnum):
    SEARCH = "SEARCH"
    WEATHER = "WEATHER"
    FLIGHT = "FLIGHT"
    HOTEL = "HOTEL"


class NormalizedProviderItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: OpaqueId = Field(default_factory=lambda: new_id("provideritem"))
    trip_id: OpaqueId
    trip_version: int = Field(ge=1)
    kind: ProviderItemKind
    provider: str = Field(min_length=1, max_length=120)
    provider_item_id: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    detail: str | None = Field(default=None, max_length=2000)
    target_entity_id: OpaqueId | None = None
    local_date: date | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    price: Money | None = None
    availability: Fact | None = None
    reference_url: str | None = Field(default=None, max_length=2048)
    handoff_url: str | None = Field(default=None, max_length=2048)
    retrieved_at: datetime
    expires_at: datetime | None = None
    evidence: tuple[Evidence, ...] = ()

    @model_validator(mode="after")
    def validate_source_and_time(self) -> "NormalizedProviderItem":
        if self.retrieved_at.tzinfo is None or (self.expires_at and self.expires_at.tzinfo is None):
            raise ValueError("Provider timestamps must be timezone-aware")
        if self.expires_at and self.expires_at <= self.retrieved_at:
            raise ValueError("Provider item expiry must follow retrieval")
        if (self.starts_at is None) != (self.ends_at is None):
            raise ValueError("Provider item times must be complete")
        if self.starts_at and (
            self.starts_at.tzinfo is None
            or self.ends_at.tzinfo is None
            or self.ends_at <= self.starts_at
        ):
            raise ValueError("Provider item times must be ordered and timezone-aware")
        if not self.evidence:
            raise ValueError("Normalized provider items require source evidence")
        evidence_ids = {item.id for item in self.evidence}
        if self.price and not set(self.price.evidence_ids).issubset(evidence_ids):
            raise ValueError("Price evidence must be embedded in the provider item")
        return self


class ProviderDataView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trip_id: OpaqueId
    version: int = Field(ge=1)
    items: tuple[NormalizedProviderItem, ...] = ()
    outcomes: tuple["ProviderRun", ...] = ()


class ProviderRun(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trip_id: OpaqueId
    trip_version: int = Field(ge=1)
    kind: ProviderItemKind
    provider: str = Field(min_length=1, max_length=120)
    status: ProviderOutcomeStatus
    error_code: str | None = Field(default=None, max_length=120)
    retrieved_at: datetime

    @model_validator(mode="after")
    def error_status_has_code(self) -> "ProviderRun":
        if self.retrieved_at.tzinfo is None:
            raise ValueError("Provider run timestamp must be timezone-aware")
        if self.status is ProviderOutcomeStatus.ERROR and not self.error_code:
            raise ValueError("Provider errors require an error code")
        return self


ProviderDataView.model_rebuild()
