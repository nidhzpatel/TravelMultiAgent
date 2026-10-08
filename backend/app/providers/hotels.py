from datetime import date, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.contracts import Fact, Money
from app.providers.base import ProviderCapabilities, ProviderResult


class HotelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    place_id: str
    check_in: date
    check_out: date
    rooms: int = Field(ge=1, le=10)
    adults: int = Field(ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    currency: str = Field(pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def valid_stay(self) -> "HotelRequest":
        if self.check_out <= self.check_in:
            raise ValueError("Hotel checkout must follow check-in")
        return self


class HotelOffer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider_offer_id: str
    property_name: str
    place_id: str
    check_in: date
    check_out: date
    rooms: int
    adults: int
    children: int
    rate_plan: str
    price: Money
    availability: Fact
    expires_at: datetime
    handoff_url: str | None = None
    evidence_ids: tuple[str, ...]


class HotelProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities
    def search(self, request: HotelRequest) -> ProviderResult[tuple[HotelOffer, ...]]: ...
