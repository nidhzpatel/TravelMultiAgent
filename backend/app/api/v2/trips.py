from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.domain.contracts import Budget, Trip, TripBrief, TripVersion, TravelerPreferences
from app.persistence.repositories import SqlAlchemyTripRepository
from app.security.identity import Principal, current_principal

router = APIRouter(prefix="/v2/trips", tags=["v2 trips"])


class CreateTripRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    brief: TripBrief
    preferences: TravelerPreferences = Field(default_factory=TravelerPreferences)
    budget: Budget
    idempotency_key: str | None = Field(default=None, min_length=16, max_length=255)


class SetMemberRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str = Field(pattern="^(EDITOR|VIEWER)$")


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
    principal: Principal = Depends(current_principal),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> TripVersion:
    trip = Trip(owner_id=principal.subject, title=request.title, brief=request.brief, preferences=request.preferences, budget=request.budget)
    try:
        return trip_repository.create(trip, request.idempotency_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("", response_model=list[TripVersion])
def list_trips(
    principal: Principal = Depends(current_principal),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> list[TripVersion]:
    return trip_repository.list_for_owner(principal.subject)


@router.get("/{trip_id}", response_model=TripVersion)
def get_trip(
    trip_id: str,
    principal: Principal = Depends(current_principal),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> TripVersion:
    trip = trip_repository.get(trip_id)
    if trip is None or trip_repository.member_role(trip_id, principal.subject) not in {"OWNER", "EDITOR", "VIEWER"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return trip


@router.get("/{trip_id}/versions/{version}", response_model=TripVersion)
def get_trip_version(
    trip_id: str,
    version: int,
    principal: Principal = Depends(current_principal),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> TripVersion:
    trip = trip_repository.get_version(trip_id, version)
    if trip is None or trip_repository.member_role(trip_id, principal.subject) not in {"OWNER", "EDITOR", "VIEWER"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip version not found")
    return trip


@router.put("/{trip_id}/members/{user_id}", status_code=status.HTTP_200_OK)
def set_member_role(
    trip_id: str,
    user_id: str,
    request: SetMemberRoleRequest,
    principal: Principal = Depends(current_principal),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> dict[str, str]:
    if trip_repository.member_role(trip_id, principal.subject) != "OWNER":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    trip_repository.set_member_role(trip_id, user_id, request.role)
    return {"role": request.role}
