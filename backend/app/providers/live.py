"""Live HTTP adapters. Vendor responses are normalized at this boundary."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable

import httpx

from app.domain.contracts import Evidence, Fact, FactStatus, Money, PriceStatus, ProviderOutcomeStatus, Provenance
from app.providers.base import ProviderCallError, ProviderCapabilities, ProviderResult
from app.providers.flights import FlightOffer, FlightRequest
from app.providers.hotels import HotelOffer, HotelRequest
from app.providers.search import SearchHit, SearchRequest
from app.providers.weather import DailyForecast, WeatherRequest, forecast_supported

JsonCall = Callable[[str, str, dict[str, Any], dict[str, str]], dict[str, Any]]


def _http_json(method: str, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.request(method, url, params=payload if method == "GET" else None, json=payload if method != "GET" else None, headers=headers)
            if response.status_code == 429:
                raise ProviderCallError("rate_limit")
            response.raise_for_status()
            value = response.json()
    except ProviderCallError:
        raise
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise ProviderCallError("provider_unavailable") from exc
    if not isinstance(value, dict):
        raise ValueError("Provider returned a non-object response")
    return value


def _evidence(source: str, reference: str | None, covered_fields: tuple[str, ...], expires_at: datetime | None = None) -> Evidence:
    return Evidence(
        source=source,
        reference_url=reference,
        expires_at=expires_at,
        covered_fields=covered_fields,
        provenance=Provenance.LIVE,
        provider_outcome=ProviderOutcomeStatus.SUCCESS,
    )


class SerperSearchProvider:
    name = "serper"
    capabilities = ProviderCapabilities(live=True, search=True, supported_markets=("GLOBAL",))

    def __init__(self, api_key: str, call: JsonCall = _http_json) -> None:
        if not api_key:
            raise ValueError("Serper API key is required")
        self.api_key = api_key
        self.call = call

    def search(self, request: SearchRequest) -> ProviderResult[tuple[SearchHit, ...]]:
        payload = self.call("POST", "https://google.serper.dev/search", {"q": request.query, "gl": request.market.lower(), "hl": request.language, "num": request.limit}, {"X-API-KEY": self.api_key, "Content-Type": "application/json"})
        hits: list[SearchHit] = []
        evidence: list[Evidence] = []
        for raw in payload.get("organic", [])[: request.limit]:
            if not isinstance(raw, dict) or not raw.get("title") or not raw.get("link"):
                continue
            item_evidence = _evidence(self.name, str(raw["link"]), ("title", "snippet", "reference_url"), datetime.now(timezone.utc) + timedelta(hours=1))
            evidence.append(item_evidence)
            hits.append(SearchHit(title=str(raw["title"]), snippet=str(raw.get("snippet", "")), reference_url=str(raw["link"]), evidence_ids=(item_evidence.id,)))
        status = ProviderOutcomeStatus.SUCCESS if hits else ProviderOutcomeStatus.NO_RESULTS
        return ProviderResult(status=status, value=tuple(hits) if hits else None, evidence=tuple(evidence))


class OpenMeteoWeatherProvider:
    name = "open-meteo"
    capabilities = ProviderCapabilities(live=True, weather=True, supported_markets=("GLOBAL",), max_forecast_days=16)

    def __init__(self, call: JsonCall = _http_json, today: Callable[[], date] = date.today) -> None:
        self.call = call
        self.today = today

    def forecast(self, request: WeatherRequest) -> ProviderResult[tuple[DailyForecast, ...]]:
        if request.latitude is None or request.longitude is None:
            return ProviderResult(status=ProviderOutcomeStatus.UNAVAILABLE, error_code="coordinates_required")
        if not forecast_supported(request, self.capabilities, self.today()):
            return ProviderResult(status=ProviderOutcomeStatus.UNAVAILABLE, error_code="forecast_horizon_unsupported")
        reference = "https://api.open-meteo.com/v1/forecast"
        payload = self.call("GET", reference, {"latitude": str(request.latitude), "longitude": str(request.longitude), "start_date": request.start_date.isoformat(), "end_date": request.end_date.isoformat(), "daily": "temperature_2m_min,temperature_2m_max,weather_code", "timezone": "auto"}, {})
        daily = payload.get("daily") if isinstance(payload.get("daily"), dict) else {}
        dates = daily.get("time", [])
        lows = daily.get("temperature_2m_min", [])
        highs = daily.get("temperature_2m_max", [])
        codes = daily.get("weather_code", [])
        retrieved = datetime.now(timezone.utc)
        expires = retrieved + timedelta(hours=3)
        evidence = _evidence(self.name, reference, ("local_date", "low_c", "high_c", "summary"), expires)
        forecasts = tuple(
            DailyForecast(local_date=date.fromisoformat(str(day)), low_c=Decimal(str(lows[index])) if index < len(lows) and lows[index] is not None else None, high_c=Decimal(str(highs[index])) if index < len(highs) and highs[index] is not None else None, summary=f"Weather code {codes[index]}" if index < len(codes) else None, evidence_ids=(evidence.id,))
            for index, day in enumerate(dates)
        )
        return ProviderResult(status=ProviderOutcomeStatus.SUCCESS if forecasts else ProviderOutcomeStatus.NO_RESULTS, value=forecasts or None, evidence=(evidence,) if forecasts else ())


class HttpFlightProvider:
    """Adapter for a configured flight aggregator that returns the documented offer fields."""

    name = "flight-api"
    capabilities = ProviderCapabilities(live=True, flights=True, booking_handoff=True, supported_markets=("GLOBAL",))

    def __init__(self, endpoint: str, api_token: str, call: JsonCall = _http_json) -> None:
        if not endpoint or not api_token:
            raise ValueError("Flight provider endpoint and token are required")
        self.endpoint, self.api_token, self.call = endpoint, api_token, call

    def search(self, request: FlightRequest) -> ProviderResult[tuple[FlightOffer, ...]]:
        payload = self.call("POST", self.endpoint, request.model_dump(mode="json"), {"Authorization": f"Bearer {self.api_token}"})
        offers: list[FlightOffer] = []
        evidence: list[Evidence] = []
        for raw in payload.get("offers", []):
            reference = raw.get("reference_url") or raw.get("handoff_url")
            expires = datetime.fromisoformat(str(raw["expires_at"]).replace("Z", "+00:00"))
            item_evidence = _evidence(self.name, reference, ("schedule", "price", "availability", "handoff_url"), expires)
            evidence.append(item_evidence)
            price = Money(amount=Decimal(str(raw["price"]["amount"])), currency=str(raw["price"]["currency"]), status=PriceStatus.VERIFIED, provenance=Provenance.LIVE, evidence_ids=(item_evidence.id,))
            offers.append(FlightOffer(provider_offer_id=str(raw["id"]), origin_place_id=request.origin_place_id, destination_place_id=request.destination_place_id, departs_at=raw["departs_at"], arrives_at=raw["arrives_at"], traveler_count=request.travelers, cabin=request.cabin, price=price, expires_at=expires, handoff_url=raw.get("handoff_url"), evidence_ids=(item_evidence.id,)))
        return ProviderResult(status=ProviderOutcomeStatus.SUCCESS if offers else ProviderOutcomeStatus.NO_RESULTS, value=tuple(offers) or None, evidence=tuple(evidence))


class HttpHotelProvider:
    """Adapter for a configured hotel aggregator that returns the documented offer fields."""

    name = "hotel-api"
    capabilities = ProviderCapabilities(live=True, hotels=True, booking_handoff=True, supported_markets=("GLOBAL",))

    def __init__(self, endpoint: str, api_token: str, call: JsonCall = _http_json) -> None:
        if not endpoint or not api_token:
            raise ValueError("Hotel provider endpoint and token are required")
        self.endpoint, self.api_token, self.call = endpoint, api_token, call

    def search(self, request: HotelRequest) -> ProviderResult[tuple[HotelOffer, ...]]:
        payload = self.call("POST", self.endpoint, request.model_dump(mode="json"), {"Authorization": f"Bearer {self.api_token}"})
        offers: list[HotelOffer] = []
        evidence: list[Evidence] = []
        for raw in payload.get("offers", []):
            reference = raw.get("reference_url") or raw.get("handoff_url")
            expires = datetime.fromisoformat(str(raw["expires_at"]).replace("Z", "+00:00"))
            item_evidence = _evidence(self.name, reference, ("property", "occupancy", "rate_plan", "price", "availability", "handoff_url"), expires)
            evidence.append(item_evidence)
            price = Money(amount=Decimal(str(raw["price"]["amount"])), currency=str(raw["price"]["currency"]), status=PriceStatus.VERIFIED, provenance=Provenance.LIVE, evidence_ids=(item_evidence.id,))
            availability = Fact(value=True, status=FactStatus.VERIFIED, evidence_ids=(item_evidence.id,), valid_at=datetime.now(timezone.utc))
            offers.append(HotelOffer(provider_offer_id=str(raw["id"]), property_name=str(raw["property_name"]), place_id=request.place_id, check_in=request.check_in, check_out=request.check_out, rooms=request.rooms, adults=request.adults, children=request.children, rate_plan=str(raw["rate_plan"]), price=price, availability=availability, expires_at=expires, handoff_url=raw.get("handoff_url"), evidence_ids=(item_evidence.id,)))
        return ProviderResult(status=ProviderOutcomeStatus.SUCCESS if offers else ProviderOutcomeStatus.NO_RESULTS, value=tuple(offers) or None, evidence=tuple(evidence))
