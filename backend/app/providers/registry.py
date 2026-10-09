"""Environment-aware provider selection with no production fixture fallback."""

from dataclasses import dataclass, field

from app.config import Settings
from app.providers.fixtures import FlightFixtureProvider, HotelFixtureProvider, SearchFixtureProvider, WeatherFixtureProvider
from app.providers.flights import FlightProvider
from app.providers.gateway import ProviderGateway
from app.providers.hotels import HotelProvider
from app.providers.live import HttpFlightProvider, HttpHotelProvider, OpenMeteoWeatherProvider, SerperSearchProvider
from app.providers.search import SearchProvider
from app.providers.weather import WeatherProvider


@dataclass(frozen=True)
class ProviderRegistry:
    search: SearchProvider | None
    weather: WeatherProvider | None
    flights: FlightProvider | None
    hotels: HotelProvider | None
    search_gateway: ProviderGateway = field(default_factory=ProviderGateway)
    weather_gateway: ProviderGateway = field(default_factory=ProviderGateway)
    flight_gateway: ProviderGateway = field(default_factory=ProviderGateway)
    hotel_gateway: ProviderGateway = field(default_factory=ProviderGateway)


def build_provider_registry(settings: Settings) -> ProviderRegistry:
    production = settings.environment.lower() == "production"
    if production:
        return ProviderRegistry(
            search=SerperSearchProvider(settings.serper_api_key) if settings.serper_api_key else None,
            weather=OpenMeteoWeatherProvider(),
            flights=HttpFlightProvider(settings.flight_provider_url, settings.flight_provider_token) if settings.flight_provider_url and settings.flight_provider_token else None,
            hotels=HttpHotelProvider(settings.hotel_provider_url, settings.hotel_provider_token) if settings.hotel_provider_url and settings.hotel_provider_token else None,
        )
    return ProviderRegistry(
        search=SearchFixtureProvider(settings.environment),
        weather=WeatherFixtureProvider(settings.environment),
        flights=FlightFixtureProvider(settings.environment),
        hotels=HotelFixtureProvider(settings.environment),
    )
