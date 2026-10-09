"""Explicit, visibly mocked development provider fixtures."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.domain.contracts import Evidence, Fact, FactStatus, Money, PriceStatus, ProviderOutcomeStatus, Provenance
from app.providers.base import ProviderCapabilities
from app.providers.base import ProviderResult
from app.providers.flights import FlightOffer, FlightRequest
from app.providers.hotels import HotelOffer, HotelRequest
from app.providers.search import SearchHit, SearchRequest
from app.providers.weather import DailyForecast, WeatherRequest


class DevelopmentFixture:
    capabilities = ProviderCapabilities(live=False)

    def __init__(self, environment: str) -> None:
        if environment == "production":
            raise RuntimeError("Development fixtures are disabled in production")

    @staticmethod
    def evidence(source: str, expires_at: datetime | None = None) -> Evidence:
        return Evidence(source=source, reference_url=None, expires_at=expires_at, provenance=Provenance.MOCK, provider_outcome=ProviderOutcomeStatus.MOCK, covered_fields=("development_fixture",))


class SearchFixtureProvider(DevelopmentFixture):
    name = "development-search-fixture"
    capabilities = ProviderCapabilities(live=False, search=True, supported_markets=("GLOBAL",))

    def search(self, request: SearchRequest) -> ProviderResult[tuple[SearchHit, ...]]:
        evidence = self.evidence(self.name)
        hit = SearchHit(title=f"Fixture result for {request.query}", snippet="Development fixture — not live provider data.", reference_url="https://example.invalid/development-fixture", evidence_ids=(evidence.id,))
        return ProviderResult(status=ProviderOutcomeStatus.MOCK, value=(hit,), evidence=(evidence,))


class WeatherFixtureProvider(DevelopmentFixture):
    name = "development-weather-fixture"
    capabilities = ProviderCapabilities(live=False, weather=True, supported_markets=("DEV",), max_forecast_days=3650)

    def forecast(self, request: WeatherRequest) -> ProviderResult[tuple[DailyForecast, ...]]:
        evidence = self.evidence(self.name)
        forecast = DailyForecast(local_date=request.start_date, low_c=Decimal("20"), high_c=Decimal("30"), summary="Development fixture", evidence_ids=(evidence.id,))
        return ProviderResult(status=ProviderOutcomeStatus.MOCK, value=(forecast,), evidence=(evidence,))


class FlightFixtureProvider(DevelopmentFixture):
    name = "development-flight-fixture"
    capabilities = ProviderCapabilities(live=False, flights=True, booking_handoff=False, supported_markets=("DEV",))

    def search(self, request: FlightRequest) -> ProviderResult[tuple[FlightOffer, ...]]:
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        evidence = self.evidence(self.name, expires)
        price = Money(amount=Decimal("100"), currency=request.currency, status=PriceStatus.ESTIMATED, provenance=Provenance.MOCK, evidence_ids=(evidence.id,))
        offer = FlightOffer(provider_offer_id="fixture-flight", origin_place_id=request.origin_place_id, destination_place_id=request.destination_place_id, departs_at=request.depart_at, arrives_at=request.depart_at + timedelta(hours=2), traveler_count=request.travelers, cabin=request.cabin, price=price, expires_at=expires, evidence_ids=(evidence.id,))
        return ProviderResult(status=ProviderOutcomeStatus.MOCK, value=(offer,), evidence=(evidence,))


class HotelFixtureProvider(DevelopmentFixture):
    name = "development-hotel-fixture"
    capabilities = ProviderCapabilities(live=False, hotels=True, booking_handoff=False, supported_markets=("DEV",))

    def search(self, request: HotelRequest) -> ProviderResult[tuple[HotelOffer, ...]]:
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        evidence = self.evidence(self.name, expires)
        price = Money(amount=Decimal("120"), currency=request.currency, status=PriceStatus.ESTIMATED, provenance=Provenance.MOCK, evidence_ids=(evidence.id,))
        availability = Fact(value=True, status=FactStatus.UNVERIFIED, evidence_ids=(evidence.id,), valid_at=datetime.now(timezone.utc))
        offer = HotelOffer(provider_offer_id="fixture-hotel", property_name="Development Fixture Hotel", place_id=request.place_id, check_in=request.check_in, check_out=request.check_out, rooms=request.rooms, adults=request.adults, children=request.children, rate_plan="fixture-rate", price=price, availability=availability, expires_at=expires, evidence_ids=(evidence.id,))
        return ProviderResult(status=ProviderOutcomeStatus.MOCK, value=(offer,), evidence=(evidence,))
