from datetime import date
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.providers.base import ProviderCapabilities, ProviderResult


class WeatherRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    place_id: str
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def valid_dates(self) -> "WeatherRequest":
        if self.end_date < self.start_date:
            raise ValueError("Weather end date precedes start date")
        return self


class DailyForecast(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    local_date: date
    low_c: Decimal | None = None
    high_c: Decimal | None = None
    summary: str | None = None
    evidence_ids: tuple[str, ...]


class WeatherProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities
    def forecast(self, request: WeatherRequest) -> ProviderResult[tuple[DailyForecast, ...]]: ...


def forecast_supported(request: WeatherRequest, capabilities: ProviderCapabilities, today: date) -> bool:
    if not capabilities.weather or capabilities.max_forecast_days is None:
        return False
    return (request.end_date - today).days <= capabilities.max_forecast_days
