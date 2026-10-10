"""Request-local provider execution and normalized result persistence."""

from pydantic import BaseModel, ConfigDict

from app.persistence.repositories import SqlAlchemyTripRepository
from app.planning.flight_specialist import FlightSpecialist
from app.planning.places_specialist import PlacesSpecialist
from app.planning.stay_specialist import StaySpecialist
from app.planning.weather_specialist import WeatherSpecialist
from app.providers.alternatives import ProviderDataView
from app.providers.flights import FlightRequest
from app.providers.hotels import HotelRequest
from app.providers.registry import ProviderRegistry
from app.providers.search import SearchRequest
from app.providers.weather import WeatherRequest
from app.observability.metrics import emit_metrics


class ProviderRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    search: SearchRequest | None = None
    weather: WeatherRequest | None = None
    flight: FlightRequest | None = None
    hotel: HotelRequest | None = None


class ProviderPlanningService:
    def __init__(self, repository: SqlAlchemyTripRepository, registry: ProviderRegistry) -> None:
        self.repository = repository
        self.registry = registry

    def refresh(self, trip_id: str, trip_version: int, request: ProviderRefreshRequest) -> ProviderDataView:
        work = (
            (request.search, PlacesSpecialist(self.registry.search_gateway), self.registry.search),
            (request.weather, WeatherSpecialist(self.registry.weather_gateway), self.registry.weather),
            (request.flight, FlightSpecialist(self.registry.flight_gateway), self.registry.flights),
            (request.hotel, StaySpecialist(self.registry.hotel_gateway), self.registry.hotels),
        )
        for provider_request, specialist, provider in work:
            if provider_request is None:
                continue
            run, items = specialist.run(trip_id, trip_version, provider_request, provider)
            emit_metrics("provider_run", {"ProviderRunCount": 1}, {"kind": run.kind.value, "provider": run.provider, "status": run.status.value})
            self.repository.replace_provider_items(trip_id, trip_version, specialist.kind, run.provider, items)
            self.repository.save_provider_run(run)
        return self.view(trip_id, trip_version)

    def view(self, trip_id: str, trip_version: int) -> ProviderDataView:
        return ProviderDataView(
            trip_id=trip_id,
            version=trip_version,
            items=self.repository.list_provider_items(trip_id, trip_version),
            outcomes=self.repository.list_provider_runs(trip_id, trip_version),
        )
