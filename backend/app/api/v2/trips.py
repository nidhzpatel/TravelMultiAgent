from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.domain.contracts import Budget, Trip, TripBrief, TripVersion, TravelerPreferences, new_id
from app.persistence.repositories import SqlAlchemyTripRepository
from app.security.identity import Principal, current_principal, enforce_rate_limit
from app.security.sessions import create_session
from app.operations.contracts import ProposalRequest
from app.operations.service import OperationValidationError, apply_operations, changed_fields, commit_replace
from app.operations.intent import resolve_message
from app.persistence.repositories import VersionConflictError

router = APIRouter(prefix="/v2/trips", tags=["v2 trips"], dependencies=[Depends(enforce_rate_limit)])


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


class TripMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=16, max_length=255)


def _proposal_response(trip_repository: SqlAlchemyTripRepository, proposal) -> dict:
    before = trip_repository.get_version(proposal.trip_id, proposal.base_version)
    if before is None:
        raise HTTPException(status_code=409, detail="Proposal base version is unavailable")
    preview = Trip.model_validate(proposal.preview)
    fields = changed_fields(before.trip, preview)
    return {
        "status": "proposal",
        "proposal_id": proposal.id,
        "base_version": proposal.base_version,
        "preview": preview.model_dump(mode="json"),
        "changed_fields": fields,
        "changes": [{"entity_id": preview.id, "fields": fields}] if fields else [],
    }


@router.post("/session", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def create_browser_session(principal: Principal = Depends(current_principal)) -> Response:
    session, csrf = create_session(principal)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.set_cookie("vm_session", session, httponly=True, secure=True, samesite="lax", max_age=8 * 3600)
    response.set_cookie("vm_csrf", csrf, httponly=False, secure=True, samesite="lax", max_age=8 * 3600)
    return response


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


@router.get("/{trip_id}/export", response_model=TripVersion)
def export_trip(
    trip_id: str,
    version: int | None = None,
    principal: Principal = Depends(current_principal),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> TripVersion:
    """Version-pinned structured export; PDF rendering moves to the export worker."""
    trip = trip_repository.get_version(trip_id, version) if version else trip_repository.get(trip_id)
    if trip is None or trip_repository.member_role(trip_id, principal.subject) not in {"OWNER", "EDITOR", "VIEWER"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return trip


@router.post("/{trip_id}/messages")
def send_trip_message(
    trip_id: str,
    request: TripMessageRequest,
    principal: Principal = Depends(current_principal),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> dict:
    trip = trip_repository.get(trip_id)
    if trip is None or trip_repository.member_role(trip_id, principal.subject) not in {"OWNER", "EDITOR"}:
        raise HTTPException(status_code=404, detail="Trip not found")
    request_identity = {"message": request.message}
    try:
        existing = trip_repository.get_proposal_by_key(trip_id, principal.subject, request.idempotency_key, request_identity)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if existing:
        return _proposal_response(trip_repository, existing)
    resolution = resolve_message(request.message, trip.version, request.idempotency_key)
    if resolution.answer:
        return {"status": "read", "message": resolution.answer, "version": trip.version}
    if resolution.question:
        return {"status": "clarifying", "message": resolution.question}
    proposal = resolution.proposal
    proposed = apply_operations(trip.trip, proposal)
    proposal_id = new_id("proposal")
    proposal_id = trip_repository.create_proposal(proposal_id, trip_id, principal.subject, proposal.idempotency_key, trip.version, proposal.model_dump(mode="json"), proposed.model_dump(mode="json"), request_identity)
    return _proposal_response(trip_repository, trip_repository.get_proposal(proposal_id, trip_id, principal.subject))


@router.post("/{trip_id}/proposals")
def preview_proposal(
    trip_id: str,
    request: ProposalRequest,
    principal: Principal = Depends(current_principal),
    trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> dict:
    trip = trip_repository.get(trip_id)
    if trip is None or trip_repository.member_role(trip_id, principal.subject) not in {"OWNER", "EDITOR"}:
        raise HTTPException(status_code=404, detail="Trip not found")
    request_payload = request.model_dump(mode="json")
    try:
        existing = trip_repository.get_proposal_by_key(trip_id, principal.subject, request.idempotency_key, request_payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if existing:
        return _proposal_response(trip_repository, existing)
    if trip.version != request.expected_version:
        raise HTTPException(status_code=409, detail="Trip changed; fetch the latest version")
    try:
        proposed = apply_operations(trip.trip, request)
    except OperationValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    proposal_id = new_id("proposal")
    proposal_id = trip_repository.create_proposal(proposal_id, trip_id, principal.subject, request.idempotency_key, trip.version, request_payload, proposed.model_dump(mode="json"))
    return _proposal_response(trip_repository, trip_repository.get_proposal(proposal_id, trip_id, principal.subject))


@router.post("/{trip_id}/proposals/{proposal_id}/commit", response_model=TripVersion)
def commit_persisted_proposal(
    trip_id: str, proposal_id: str, principal: Principal = Depends(current_principal), trip_repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> TripVersion:
    if trip_repository.member_role(trip_id, principal.subject) not in {"OWNER", "EDITOR"}:
        raise HTTPException(status_code=404, detail="Proposal not found")
    proposal = trip_repository.get_proposal(proposal_id, trip_id, principal.subject)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.committed_version:
        committed = trip_repository.get_version(trip_id, proposal.committed_version)
        if committed:
            return committed
    trip = trip_repository.get(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    request = ProposalRequest.model_validate(proposal.payload)
    try:
        committed = commit_replace(trip_repository, trip.trip, request)
        trip_repository.mark_proposal_committed(proposal_id, committed.version)
        return committed
    except (OperationValidationError, VersionConflictError) as exc:
        raise HTTPException(status_code=409 if isinstance(exc, VersionConflictError) else 422, detail=str(exc)) from exc


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
