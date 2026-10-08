"""Provider boundary shared by production adapters."""

from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.contracts import Evidence, ProviderOutcomeStatus

T = TypeVar("T")


class ProviderResult(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: ProviderOutcomeStatus
    value: T | None = None
    evidence: tuple[Evidence, ...] = ()
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "ProviderResult[T]":
        if self.status in {ProviderOutcomeStatus.SUCCESS, ProviderOutcomeStatus.MOCK} and self.value is None:
            raise ValueError("Successful provider outcomes require a value")
        if self.status in {ProviderOutcomeStatus.NO_RESULTS, ProviderOutcomeStatus.UNAVAILABLE, ProviderOutcomeStatus.ERROR} and self.value is not None:
            raise ValueError("Unsuccessful provider outcomes cannot carry a value")
        if self.status is ProviderOutcomeStatus.ERROR and not self.error_code:
            raise ValueError("Provider errors require an error code")
        return self


class ProviderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    live: bool
    search: bool = False
    weather: bool = False
    flights: bool = False
    hotels: bool = False
    booking_handoff: bool = False
    supported_markets: tuple[str, ...] = ()
    max_forecast_days: int | None = None


class ProviderMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reference: str | None = None
