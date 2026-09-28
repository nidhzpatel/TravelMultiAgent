from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.domain.contracts import Budget, Trip, TripBrief, TripVersion, TravelerPreferences
from app.persistence.repositories import SqlAlchemyTripRepository

router = APIRouter(prefix="/v2/trips", tags=["v2 trips"])


class CreateTripRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    brief: TripBrief
    preferences: TravelerPreferences = Field(default_factory=TravelerPreferences)
    budget: Budget
    idempotency_key: str | None = Field(default=None, min_length=16, max_length=255)


def current_user_id(x_voyagemind_user: str = Header(min_length=1, max_length=255)) -> str:
    """Temporary identity adapter; replaced by verified OIDC session in P2."""
    return x_voyagemind_user


@lru_cache
def repository() -> SqlAlchemyTripRepository:
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL must be configured for v2 trip endpoints")
    return SqlAlchemyTripRepository(database_url)


def get_repository() -> SqlAlchemyTripRepository:
    try:
        return repository()
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("", response_model=TripVersion, status_code=status.HTTP_201_CREATED)
def create_trip(
    request: CreateTripRequest,
    owner_id: str = Depends(current_user_id),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> TripVersion:
    trip = Trip(owner_id=owner_id, title=request.title, brief=request.brief, preferences=request.preferences, budget=request.budget)
    try:
        return trip_repository.create(trip, request.idempotency_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=list[TripVersion])
def list_trips(
    owner_id: str = Depends(current_user_id),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> list[TripVersion]:
    return trip_repository.list_for_owner(owner_id)


@router.get("/{trip_id}", response_model=TripVersion)
def get_trip(
    trip_id: str,
    owner_id: str = Depends(current_user_id),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> TripVersion:
    trip = trip_repository.get(trip_id)
    if trip is None or trip.trip.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return trip


@router.get("/{trip_id}/versions/{version}", response_model=TripVersion)
def get_trip_version(
    trip_id: str,
    version: int,
    owner_id: str = Depends(current_user_id),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> TripVersion:
    trip = trip_repository.get_version(trip_id, version)
    if trip is None or trip.trip.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip version not found")
    return trip
