"""Typed flight specialist preserving offer scope, expiry, and evidence."""

from app.providers.alternatives import NormalizedProviderItem, ProviderItemKind
from app.providers.flights import FlightProvider, FlightRequest
from app.planning.provider_support import ProviderSpecialist


class FlightSpecialist(ProviderSpecialist[tuple]):
    kind = ProviderItemKind.FLIGHT

    def run(self, trip_id: str, trip_version: int, request: FlightRequest, provider: FlightProvider | None):
        def normalize(result):
            evidence = {item.id: item for item in result.evidence}
            return tuple(
                NormalizedProviderItem(
                    trip_id=trip_id,
                    trip_version=trip_version,
                    kind=self.kind,
                    provider=provider.name,
                    provider_item_id=offer.provider_offer_id,
                    title=f"{offer.origin_place_id} to {offer.destination_place_id}",
                    detail=f"{offer.cabin} · {offer.traveler_count} traveler(s)",
                    starts_at=offer.departs_at,
                    ends_at=offer.arrives_at,
                    price=offer.price,
                    handoff_url=offer.handoff_url,
                    retrieved_at=min(evidence[item].retrieved_at for item in offer.evidence_ids),
                    expires_at=offer.expires_at,
                    evidence=tuple(evidence[item] for item in offer.evidence_ids),
                )
                for offer in result.value
            )
        return self.execute(trip_id, trip_version, request, provider, lambda: provider.search(request), normalize)
