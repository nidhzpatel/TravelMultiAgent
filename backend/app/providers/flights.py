from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.contracts import Money
from app.providers.base import ProviderCapabilities, ProviderResult


class FlightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    origin_place_id: str
    destination_place_id: str
    depart_at: datetime
    return_at: datetime | None = None
    travelers: int = Field(ge=1, le=20)
    cabin: Literal["economy", "premium_economy", "business", "first"] = "economy"
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def valid_schedule(self) -> "FlightRequest":
        if self.depart_at.tzinfo is None or (self.return_at and self.return_at.tzinfo is None):
            raise ValueError("Flight request times must be timezone-aware")
        if self.return_at and self.return_at <= self.depart_at:
            raise ValueError("Flight return must follow departure")
        return self


class FlightOffer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider_offer_id: str
    origin_place_id: str
    destination_place_id: str
    departs_at: datetime
    arrives_at: datetime
    traveler_count: int = Field(ge=1, le=20)
    cabin: Literal["economy", "premium_economy", "business", "first"]
    price: Money
    expires_at: datetime
    handoff_url: str | None = None
    evidence_ids: tuple[str, ...]

    @model_validator(mode="after")
    def valid_offer(self) -> "FlightOffer":
        if self.departs_at.tzinfo is None or self.arrives_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("Flight offer timestamps must be timezone-aware")
        if self.arrives_at <= self.departs_at:
            raise ValueError("Flight arrival must follow departure")
        return self


class FlightProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities
    def search(self, request: FlightRequest) -> ProviderResult[tuple[FlightOffer, ...]]: ...
