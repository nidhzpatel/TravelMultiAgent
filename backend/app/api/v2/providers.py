"""Provider-backed alternatives and forecasts for an accepted trip version."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException

from app.api.v2.trips import get_repository
from app.config import get_settings
from app.persistence.repositories import SqlAlchemyTripRepository
from app.planning.provider_service import ProviderPlanningService, ProviderRefreshRequest
from app.providers.alternatives import ProviderDataView
from app.providers.registry import ProviderRegistry, build_provider_registry
from app.security.identity import Principal, current_principal, enforce_rate_limit

router = APIRouter(prefix="/v2/trips", tags=["v2 providers"], dependencies=[Depends(enforce_rate_limit)])


@lru_cache
def provider_registry() -> ProviderRegistry:
    return build_provider_registry(get_settings())


def get_provider_registry() -> ProviderRegistry:
    return provider_registry()


def _authorized_trip(trip_id: str, principal: Principal, repository: SqlAlchemyTripRepository):
    trip = repository.get(trip_id)
    if trip is None or repository.member_role(trip_id, principal.subject) not in {"OWNER", "EDITOR", "VIEWER"}:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.get("/{trip_id}/provider-data", response_model=ProviderDataView)
def get_provider_data(
    trip_id: str,
    version: int | None = None,
    principal: Principal = Depends(current_principal),
    repository: SqlAlchemyTripRepository = Depends(get_repository),
) -> ProviderDataView:
    current = _authorized_trip(trip_id, principal, repository)
    selected_version = version or current.version
    if repository.get_version(trip_id, selected_version) is None:
        raise HTTPException(status_code=404, detail="Trip version not found")
    return ProviderPlanningService(repository, provider_registry()).view(trip_id, selected_version)


@router.post("/{trip_id}/provider-data/refresh", response_model=ProviderDataView)
def refresh_provider_data(
    trip_id: str,
    request: ProviderRefreshRequest,
    principal: Principal = Depends(current_principal),
    repository: SqlAlchemyTripRepository = Depends(get_repository),
    registry: ProviderRegistry = Depends(get_provider_registry),
) -> ProviderDataView:
    current = _authorized_trip(trip_id, principal, repository)
    if repository.member_role(trip_id, principal.subject) not in {"OWNER", "EDITOR"}:
        raise HTTPException(status_code=403, detail="Trip edit access required")
    return ProviderPlanningService(repository, registry).refresh(trip_id, current.version, request)
