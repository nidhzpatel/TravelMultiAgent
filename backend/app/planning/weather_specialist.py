"""Typed weather specialist with explicit forecast-horizon failures."""

from app.providers.alternatives import NormalizedProviderItem, ProviderItemKind
from app.providers.weather import WeatherProvider, WeatherRequest
from app.planning.provider_support import ProviderSpecialist


class WeatherSpecialist(ProviderSpecialist[tuple]):
    kind = ProviderItemKind.WEATHER

    def run(self, trip_id: str, trip_version: int, request: WeatherRequest, provider: WeatherProvider | None):
        def normalize(result):
            evidence = {item.id: item for item in result.evidence}
            return tuple(
                NormalizedProviderItem(
                    trip_id=trip_id,
                    trip_version=trip_version,
                    kind=self.kind,
                    provider=provider.name,
                    provider_item_id=f"{request.place_id}:{forecast.local_date.isoformat()}",
                    title=forecast.summary or "Forecast unavailable",
                    detail=f"{forecast.low_c if forecast.low_c is not None else '?'}–{forecast.high_c if forecast.high_c is not None else '?'} °C",
                    local_date=forecast.local_date,
                    retrieved_at=min(evidence[item].retrieved_at for item in forecast.evidence_ids),
                    expires_at=min((evidence[item].expires_at for item in forecast.evidence_ids if evidence[item].expires_at), default=None),
                    evidence=tuple(evidence[item] for item in forecast.evidence_ids),
                )
                for forecast in result.value
            )
        return self.execute(trip_id, trip_version, request, provider, lambda: provider.forecast(request), normalize)
