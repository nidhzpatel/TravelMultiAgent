"""Shared helpers for request-local provider specialists."""

from datetime import datetime, timezone
from typing import Callable, Generic, TypeVar

from pydantic import BaseModel

from app.domain.contracts import ProviderOutcomeStatus
from app.providers.alternatives import NormalizedProviderItem, ProviderItemKind, ProviderRun
from app.providers.base import ProviderResult
from app.providers.gateway import ProviderGateway

T = TypeVar("T")


class ProviderSpecialist(Generic[T]):
    kind: ProviderItemKind

    def __init__(self, gateway: ProviderGateway[T] | None = None) -> None:
        self.gateway = gateway or ProviderGateway()

    def execute(
        self,
        trip_id: str,
        trip_version: int,
        request: BaseModel,
        provider: object | None,
        call: Callable[[], ProviderResult[T]],
        normalize: Callable[[ProviderResult[T]], tuple[NormalizedProviderItem, ...]],
    ) -> tuple[ProviderRun, tuple[NormalizedProviderItem, ...]]:
        provider_name = getattr(provider, "name", f"unconfigured-{self.kind.value.lower()}")
        if provider is None:
            result: ProviderResult[T] = ProviderResult(status=ProviderOutcomeStatus.UNAVAILABLE, error_code="provider_not_configured")
        elif not getattr(getattr(provider, "capabilities", None), {
            ProviderItemKind.SEARCH: "search",
            ProviderItemKind.WEATHER: "weather",
            ProviderItemKind.FLIGHT: "flights",
            ProviderItemKind.HOTEL: "hotels",
        }[self.kind], False):
            result = ProviderResult(status=ProviderOutcomeStatus.UNAVAILABLE, error_code="unsupported_capability")
        elif getattr(request, "market", None) and "GLOBAL" not in provider.capabilities.supported_markets and request.market not in provider.capabilities.supported_markets:
            result = ProviderResult(status=ProviderOutcomeStatus.UNAVAILABLE, error_code="unsupported_market")
        else:
            result = self.gateway.execute(provider_name, request, call)
        try:
            items = normalize(result) if result.value is not None else ()
        except Exception:
            result = ProviderResult(status=ProviderOutcomeStatus.ERROR, error_code="normalization_error")
            items = ()
        run = ProviderRun(trip_id=trip_id, trip_version=trip_version, kind=self.kind, provider=provider_name, status=result.status, error_code=result.error_code, retrieved_at=datetime.now(timezone.utc))
        return run, items
