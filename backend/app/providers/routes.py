"""Directed route provider contract and freshness-aware cache."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.providers.base import ProviderResult


class RouteStatus(StrEnum):
    REACHABLE = "REACHABLE"
    UNREACHABLE = "UNREACHABLE"
    UNKNOWN = "UNKNOWN"


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    origin_place_id: str
    destination_place_id: str
    mode: str = "drive"
    depart_at: datetime


class RouteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    origin_place_id: str
    destination_place_id: str
    mode: str
    status: RouteStatus
    duration_minutes: int | None = Field(default=None, ge=0)
    distance_km: Decimal | None = Field(default=None, ge=0)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def duration_matches_status(self) -> "RouteResult":
        if self.status is RouteStatus.REACHABLE and self.duration_minutes is None:
            raise ValueError("Reachable routes require a provider duration")
        if self.status is not RouteStatus.REACHABLE and self.duration_minutes is not None:
            raise ValueError("Unknown or unreachable routes cannot claim a duration")
        return self


class RouteProvider(Protocol):
    def route_matrix(self, requests: tuple[RouteRequest, ...]) -> ProviderResult[tuple[RouteResult, ...]]: ...


class RouteCache:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str, str, str], RouteResult] = {}

    @staticmethod
    def _key(request: RouteRequest) -> tuple[str, str, str, str]:
        return (request.origin_place_id, request.destination_place_id, request.mode, request.depart_at.isoformat())

    def put(self, request: RouteRequest, result: RouteResult, ttl: timedelta) -> None:
        self._items[self._key(request)] = result.model_copy(update={"expires_at": result.retrieved_at + ttl})

    def get(self, request: RouteRequest, at: datetime | None = None) -> RouteResult | None:
        result = self._items.get(self._key(request))
        now = at or datetime.now(timezone.utc)
        return result if result and (result.expires_at is None or result.expires_at > now) else None
