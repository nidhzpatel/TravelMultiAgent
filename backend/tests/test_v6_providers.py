from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import time
import unittest

from pydantic import ValidationError

from app.config import Settings
from app.domain.contracts import Budget, Money, PriceStatus, ProviderOutcomeStatus, Provenance, Trip, TripBrief
from app.persistence.repositories import SqlAlchemyTripRepository
from app.planning.provider_service import ProviderPlanningService, ProviderRefreshRequest
from app.providers.base import ProviderCallError, ProviderCapabilities, ProviderResult
from app.providers.fixtures import DevelopmentFixture
from app.providers.flights import FlightOffer, FlightRequest
from app.providers.gateway import ProviderGateway, select_provider
from app.providers.hotels import HotelRequest
from app.providers.live import HttpFlightProvider, HttpHotelProvider, OpenMeteoWeatherProvider, SerperSearchProvider
from app.providers.registry import ProviderRegistry, build_provider_registry
from app.providers.search import SearchRequest
from app.providers.weather import WeatherRequest, forecast_supported


class ProviderContractTests(unittest.TestCase):
    def test_gateway_bounds_timeout_and_normalizes_malformed_failures(self) -> None:
        gateway = ProviderGateway(timeout_seconds=0.01)
        request = SearchRequest(query="Goa", market="IN")
        started = time.monotonic()
        timed_out = gateway.execute("search", request, lambda: (time.sleep(0.1), ProviderResult(status=ProviderOutcomeStatus.NO_RESULTS))[1])
        self.assertEqual(timed_out.status, ProviderOutcomeStatus.UNAVAILABLE)
        self.assertLess(time.monotonic() - started, 0.08)
        malformed = gateway.execute("broken", request, lambda: (_ for _ in ()).throw(ValueError("bad response")))
        self.assertEqual(malformed.error_code, "provider_error")
        limited = gateway.execute("limited", request, lambda: (_ for _ in ()).throw(ProviderCallError("rate_limit")))
        self.assertEqual(limited.error_code, "rate_limit")

    def test_no_inventory_and_rate_limit_remain_explicit_without_mock_fallback(self) -> None:
        request = SearchRequest(query="Goa", market="IN")
        gateway = ProviderGateway()
        empty = gateway.execute("live", request, lambda: ProviderResult(status=ProviderOutcomeStatus.NO_RESULTS))
        limited = gateway.execute("limited", request, lambda: ProviderResult(status=ProviderOutcomeStatus.ERROR, error_code="rate_limit"))
        self.assertEqual(empty.status, ProviderOutcomeStatus.NO_RESULTS)
        self.assertEqual(limited.error_code, "rate_limit")
        fixture = object()
        with self.assertRaises(RuntimeError):
            select_provider("production", None, fixture)
        with self.assertRaises(RuntimeError):
            DevelopmentFixture("production")

    def test_cache_isolated_by_provider_and_complete_request_scope(self) -> None:
        gateway = ProviderGateway()
        first = SearchRequest(query="hotels", market="IN", language="en")
        second = first.model_copy(update={"market": "US"})
        calls = {"count": 0}
        def call():
            calls["count"] += 1
            return ProviderResult(status=ProviderOutcomeStatus.NO_RESULTS)
        gateway.execute("a", first, call)
        gateway.execute("a", first, call)
        gateway.execute("b", first, call)
        gateway.execute("a", second, call)
        self.assertEqual(calls["count"], 3)

    def test_dated_occupancy_and_forecast_capability_are_validated(self) -> None:
        stay = HotelRequest(place_id="goa", check_in=date(2026, 1, 1), check_out=date(2026, 1, 3), rooms=2, adults=3, children=1, currency="INR")
        self.assertEqual((stay.rooms, stay.adults, stay.children), (2, 3, 1))
        with self.assertRaises(ValidationError):
            HotelRequest(place_id="goa", check_in=date(2026, 1, 3), check_out=date(2026, 1, 3), rooms=1, adults=1, currency="INR")
        weather = WeatherRequest(place_id="goa", start_date=date(2026, 1, 1), end_date=date(2026, 1, 20))
        capabilities = ProviderCapabilities(live=True, weather=True, max_forecast_days=10)
        self.assertFalse(forecast_supported(weather, capabilities, date(2026, 1, 1)))

    def test_expired_or_changed_flight_offers_require_revalidation(self) -> None:
        now = datetime.now(timezone.utc)
        request = FlightRequest(origin_place_id="a", destination_place_id="b", depart_at=now + timedelta(days=2), travelers=1, currency="USD")
        money = Money(amount=Decimal("100"), currency="USD", status=PriceStatus.ESTIMATED, provenance=Provenance.LIVE)
        def offer(price: Money, expires: datetime) -> FlightOffer:
            return FlightOffer(provider_offer_id="offer", origin_place_id="a", destination_place_id="b", departs_at=now + timedelta(days=2), arrives_at=now + timedelta(days=2, hours=2), traveler_count=1, cabin="economy", price=price, expires_at=expires, evidence_ids=())
        gateway = ProviderGateway()
        expired = gateway.execute("flight", request, lambda: ProviderResult(status=ProviderOutcomeStatus.SUCCESS, value=(offer(money, now - timedelta(seconds=1)),)))
        self.assertEqual(expired.error_code, "expired_result")
        fresh = gateway.execute("flight", request, lambda: ProviderResult(status=ProviderOutcomeStatus.SUCCESS, value=(offer(money, now + timedelta(minutes=5)),)))
        self.assertEqual(fresh.value[0].price.amount, Decimal("100"))

    def test_live_adapters_preserve_provider_reference_time_and_status(self) -> None:
        now = datetime.now(timezone.utc)
        search = SerperSearchProvider("key", call=lambda *_: {"organic": [{"title": "Goa guide", "snippet": "Live result", "link": "https://source.example/goa"}]})
        searched = search.search(SearchRequest(query="Goa", market="IN"))
        self.assertEqual(searched.status, ProviderOutcomeStatus.SUCCESS)
        self.assertEqual(searched.evidence[0].reference_url, "https://source.example/goa")
        self.assertEqual(searched.value[0].evidence_ids, (searched.evidence[0].id,))

        weather = OpenMeteoWeatherProvider(call=lambda *_: {"daily": {"time": [date.today().isoformat()], "temperature_2m_min": [20], "temperature_2m_max": [31], "weather_code": [1]}}, today=date.today)
        forecast = weather.forecast(WeatherRequest(place_id="goa", latitude=Decimal("15.49"), longitude=Decimal("73.82"), start_date=date.today(), end_date=date.today()))
        self.assertEqual(forecast.status, ProviderOutcomeStatus.SUCCESS)
        self.assertEqual(forecast.value[0].evidence_ids, (forecast.evidence[0].id,))

        flight = HttpFlightProvider("https://flight.example/search", "token", call=lambda *_: {"offers": [{"id": "live-flight", "departs_at": (now + timedelta(days=1)).isoformat(), "arrives_at": (now + timedelta(days=1, hours=2)).isoformat(), "expires_at": (now + timedelta(minutes=15)).isoformat(), "price": {"amount": "125.40", "currency": "USD"}, "reference_url": "https://flight.example/live-flight", "handoff_url": "https://flight.example/book/live-flight"}]})
        flights = flight.search(FlightRequest(origin_place_id="a", destination_place_id="b", depart_at=now + timedelta(days=1), travelers=1, currency="USD"))
        self.assertEqual(flights.value[0].price.status, PriceStatus.VERIFIED)
        self.assertEqual(flights.evidence[0].reference_url, "https://flight.example/live-flight")

        hotel = HttpHotelProvider("https://hotel.example/search", "token", call=lambda *_: {"offers": [{"id": "live-hotel", "property_name": "Live Hotel", "rate_plan": "refundable", "expires_at": (now + timedelta(minutes=15)).isoformat(), "price": {"amount": "200", "currency": "USD"}, "reference_url": "https://hotel.example/live-hotel"}]})
        hotels = hotel.search(HotelRequest(place_id="goa", check_in=date.today() + timedelta(days=1), check_out=date.today() + timedelta(days=2), rooms=1, adults=2, currency="USD"))
        self.assertEqual(hotels.value[0].availability.status.value, "VERIFIED")
        self.assertEqual(hotels.evidence[0].reference_url, "https://hotel.example/live-hotel")

    def test_fixture_results_are_visible_and_persisted_by_trip_version(self) -> None:
        repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        repository.create_schema_for_test()
        trip = Trip(owner_id="user", title="Goa", brief=TripBrief(destination_text="Goa"), budget=Budget(target=Money(amount=Decimal("1000"), currency="USD", status=PriceStatus.USER_PROVIDED, provenance=Provenance.USER)))
        repository.create(trip)
        registry = build_provider_registry(Settings(environment="development"))
        view = ProviderPlanningService(repository, registry).refresh(trip.id, 1, ProviderRefreshRequest(search=SearchRequest(query="Goa", market="IN"), flight=FlightRequest(origin_place_id="a", destination_place_id="b", depart_at=datetime.now(timezone.utc) + timedelta(days=2), travelers=1, currency="USD")))
        self.assertEqual({item.kind.value for item in view.items}, {"SEARCH", "FLIGHT"})
        self.assertTrue(all(item.evidence[0].provenance is Provenance.MOCK for item in view.items))
        self.assertTrue(all(run.status is ProviderOutcomeStatus.MOCK for run in view.outcomes))
        self.assertEqual(ProviderPlanningService(repository, registry).view(trip.id, 1), view)

    def test_unconfigured_production_provider_is_explicitly_unavailable(self) -> None:
        registry = build_provider_registry(Settings(environment="production"))
        self.assertIsNone(registry.flights)
        repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        repository.create_schema_for_test()
        trip = Trip(owner_id="user", title="Goa", brief=TripBrief(destination_text="Goa"), budget=Budget(target=Money(amount=Decimal("1000"), currency="USD", status=PriceStatus.USER_PROVIDED, provenance=Provenance.USER)))
        repository.create(trip)
        request = FlightRequest(origin_place_id="a", destination_place_id="b", depart_at=datetime.now(timezone.utc) + timedelta(days=2), travelers=1, currency="USD")
        view = ProviderPlanningService(repository, ProviderRegistry(None, None, None, None)).refresh(trip.id, 1, ProviderRefreshRequest(flight=request))
        self.assertEqual(view.items, ())
        self.assertEqual(view.outcomes[0].status, ProviderOutcomeStatus.UNAVAILABLE)
        self.assertEqual(view.outcomes[0].error_code, "provider_not_configured")

    def test_unsupported_capability_and_repriced_offer_are_persisted_explicitly(self) -> None:
        repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        repository.create_schema_for_test()
        trip = Trip(owner_id="user", title="Goa", brief=TripBrief(destination_text="Goa"), budget=Budget(target=Money(amount=Decimal("1000"), currency="USD", status=PriceStatus.USER_PROVIDED, provenance=Provenance.USER)))
        repository.create(trip)
        request = FlightRequest(origin_place_id="a", destination_place_id="b", depart_at=datetime.now(timezone.utc) + timedelta(days=2), travelers=1, currency="USD")

        class Unsupported:
            name = "unsupported"
            capabilities = ProviderCapabilities(live=True, flights=False)
            def search(self, _request):
                raise AssertionError("unsupported provider must not be called")

        unavailable = ProviderPlanningService(repository, ProviderRegistry(None, None, Unsupported(), None)).refresh(trip.id, 1, ProviderRefreshRequest(flight=request))
        self.assertEqual(unavailable.outcomes[0].error_code, "unsupported_capability")

        registry = build_provider_registry(Settings(environment="development"))
        first = ProviderPlanningService(repository, registry).refresh(trip.id, 1, ProviderRefreshRequest(flight=request))
        original = first.items[0]
        changed_price = original.price.model_copy(update={"amount": Decimal("175")})
        changed = original.model_copy(update={"price": changed_price, "provider": "replacement-provider"})
        repository.replace_provider_items(trip.id, 1, original.kind, changed.provider, (changed,))
        reloaded = ProviderPlanningService(repository, registry).view(trip.id, 1)
        self.assertEqual(len([item for item in reloaded.items if item.kind.value == "FLIGHT"]), 1)
        replacement = next(item for item in reloaded.items if item.kind.value == "FLIGHT")
        self.assertEqual(replacement.provider, "replacement-provider")
        self.assertEqual(replacement.price.amount, Decimal("175"))


if __name__ == "__main__":
    unittest.main()
