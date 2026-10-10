"""Owner-managed trip collaboration and revocable one-time invitations."""

from datetime import timedelta
import hashlib
import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.v2.trips import get_repository
from app.collaboration.contracts import ShareInvitation, TripMember
from app.domain.contracts import new_id
from app.persistence.models import TripShareRecord, utcnow
from app.persistence.repositories import SqlAlchemyTripRepository
from app.security.identity import Principal, current_principal, enforce_rate_limit

router = APIRouter(prefix="/v2", tags=["v2 collaboration"], dependencies=[Depends(enforce_rate_limit)])


class CreateShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["EDITOR", "VIEWER"]
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class CreatedShare(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invitation: ShareInvitation
    token: str


def _share(row: TripShareRecord) -> ShareInvitation:
    return ShareInvitation(id=row.id, trip_id=row.trip_id, role=row.role, expires_at=row.expires_at, revoked_at=row.revoked_at, accepted_by=row.accepted_by, accepted_at=row.accepted_at, created_at=row.created_at)


def _owner(trip_id: str, principal: Principal, repository: SqlAlchemyTripRepository) -> None:
    if repository.get(trip_id) is None or repository.member_role(trip_id, principal.subject) != "OWNER":
        raise HTTPException(status_code=404, detail="Trip not found")


@router.get("/trips/{trip_id}/members", response_model=tuple[TripMember, ...])
def list_members(trip_id: str, principal: Principal = Depends(current_principal), repository: SqlAlchemyTripRepository = Depends(get_repository)) -> tuple[TripMember, ...]:
    _owner(trip_id, principal, repository)
    return tuple(TripMember(user_id=user_id, role=role) for user_id, role in repository.list_members(trip_id))


@router.delete("/trips/{trip_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(trip_id: str, user_id: str, principal: Principal = Depends(current_principal), repository: SqlAlchemyTripRepository = Depends(get_repository)) -> None:
    _owner(trip_id, principal, repository)
    try:
        if not repository.remove_member(trip_id, user_id):
            raise HTTPException(status_code=404, detail="Member not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/trips/{trip_id}/shares", response_model=CreatedShare, status_code=status.HTTP_201_CREATED)
def create_share(request: CreateShareRequest, trip_id: str, principal: Principal = Depends(current_principal), repository: SqlAlchemyTripRepository = Depends(get_repository)) -> CreatedShare:
    _owner(trip_id, principal, repository)
    token = secrets.token_urlsafe(32)
    now = utcnow()
    row = TripShareRecord(id=new_id("share"), trip_id=trip_id, created_by=principal.subject, token_hash=hashlib.sha256(token.encode()).hexdigest(), role=request.role, expires_at=now + timedelta(hours=request.expires_in_hours), created_at=now)
    repository.create_share(row)
    return CreatedShare(invitation=_share(row), token=token)


@router.get("/trips/{trip_id}/shares", response_model=tuple[ShareInvitation, ...])
def list_shares(trip_id: str, principal: Principal = Depends(current_principal), repository: SqlAlchemyTripRepository = Depends(get_repository)) -> tuple[ShareInvitation, ...]:
    _owner(trip_id, principal, repository)
    return tuple(_share(row) for row in repository.list_shares(trip_id))


@router.delete("/trips/{trip_id}/shares/{share_id}", response_model=ShareInvitation)
def revoke_share(trip_id: str, share_id: str, principal: Principal = Depends(current_principal), repository: SqlAlchemyTripRepository = Depends(get_repository)) -> ShareInvitation:
    _owner(trip_id, principal, repository)
    existing = repository.get_share(share_id)
    if existing is None or existing.trip_id != trip_id:
        raise HTTPException(status_code=404, detail="Share invitation not found")
    revoked = repository.revoke_share(share_id)
    assert revoked is not None
    return _share(revoked)


@router.post("/shares/{token}/accept")
def accept_share(token: str, principal: Principal = Depends(current_principal), repository: SqlAlchemyTripRepository = Depends(get_repository)) -> dict[str, str]:
    try:
        trip_id, role = repository.accept_share(hashlib.sha256(token.encode()).hexdigest(), principal.subject)
        return {"trip_id": trip_id, "role": role}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Share invitation not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc
