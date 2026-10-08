"""Place resolution boundary with coordinates and IANA time zones."""

from decimal import Decimal
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.contracts import Evidence, new_id
from app.providers.base import ProviderResult


class ResolvedPlace(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(default_factory=lambda: new_id("place"))
    name: str = Field(min_length=1, max_length=300)
    provider_place_id: str = Field(min_length=1, max_length=300)
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    timezone: str
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def valid_timezone(self) -> "ResolvedPlace":
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Place timezone must be an IANA timezone") from exc
        return self


class PlacesProvider(Protocol):
    def resolve(self, query: str) -> ProviderResult[ResolvedPlace]: ...
