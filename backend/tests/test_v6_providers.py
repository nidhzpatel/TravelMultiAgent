from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import time
import unittest

from pydantic import ValidationError

from app.domain.contracts import Money, PriceStatus, ProviderOutcomeStatus, Provenance
from app.providers.base import ProviderCapabilities, ProviderResult
from app.providers.fixtures import DevelopmentFixture
from app.providers.flights import FlightOffer, FlightRequest
from app.providers.gateway import ProviderGateway, select_provider
from app.providers.hotels import HotelRequest
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


if __name__ == "__main__":
    unittest.main()
