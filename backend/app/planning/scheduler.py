"""Timezone-aware scheduled items and deterministic buffer placement."""

from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.contracts import new_id
from app.providers.routes import RouteResult, RouteStatus


class OpeningWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    opens_at: datetime
    closes_at: datetime

    @model_validator(mode="after")
    def valid_window(self) -> "OpeningWindow":
        if self.opens_at.tzinfo is None or self.closes_at.tzinfo is None or self.closes_at <= self.opens_at:
            raise ValueError("Opening windows require ordered timezone-aware timestamps")
        return self


class PlannedItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(default_factory=lambda: new_id("item"))
    kind: Literal["activity", "restaurant", "flight", "hotel", "transport"]
    entity_id: str
    place_id: str
    start_at: datetime
    end_at: datetime
    opening_windows: tuple[OpeningWindow, ...] = ()
    critical: bool = True

    @model_validator(mode="after")
    def valid_times(self) -> "PlannedItem":
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None or self.end_at <= self.start_at:
            raise ValueError("Scheduled items require ordered timezone-aware timestamps")
        return self


class PlannedDay(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    local_date: date
    timezone: str
    items: tuple[PlannedItem, ...]


def schedule_after(previous: PlannedItem, item: PlannedItem, route: RouteResult, buffer_minutes: int = 15) -> PlannedItem:
    if route.status is not RouteStatus.REACHABLE or route.duration_minutes is None:
        raise ValueError("A provider route duration is required before scheduling")
    earliest = previous.end_at + timedelta(minutes=route.duration_minutes + buffer_minutes)
    start = max(item.start_at, earliest)
    duration = item.end_at - item.start_at
    candidate = item.model_copy(update={"start_at": start, "end_at": start + duration})
    if candidate.opening_windows and not any(window.opens_at <= candidate.start_at and candidate.end_at <= window.closes_at for window in candidate.opening_windows):
        raise ValueError("Scheduled item does not fit an opening window")
    return candidate
