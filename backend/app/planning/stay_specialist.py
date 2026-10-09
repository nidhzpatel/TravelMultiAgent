"""Typed stay specialist preserving occupancy, rate, availability, and evidence."""

from app.providers.alternatives import NormalizedProviderItem, ProviderItemKind
from app.providers.hotels import HotelProvider, HotelRequest
from app.planning.provider_support import ProviderSpecialist


class StaySpecialist(ProviderSpecialist[tuple]):
    kind = ProviderItemKind.HOTEL

    def run(self, trip_id: str, trip_version: int, request: HotelRequest, provider: HotelProvider | None):
        def normalize(result):
            evidence = {item.id: item for item in result.evidence}
            return tuple(
                NormalizedProviderItem(
                    trip_id=trip_id,
                    trip_version=trip_version,
                    kind=self.kind,
                    provider=provider.name,
                    provider_item_id=offer.provider_offer_id,
                    title=offer.property_name,
                    detail=f"{offer.rate_plan} · {offer.rooms} room(s), {offer.adults} adult(s), {offer.children} child(ren)",
                    price=offer.price,
                    availability=offer.availability,
                    handoff_url=offer.handoff_url,
                    retrieved_at=min(evidence[item].retrieved_at for item in offer.evidence_ids),
                    expires_at=offer.expires_at,
                    evidence=tuple(evidence[item] for item in offer.evidence_ids),
                )
                for offer in result.value
            )
        return self.execute(trip_id, trip_version, request, provider, lambda: provider.search(request), normalize)
