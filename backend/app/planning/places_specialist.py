"""Typed search specialist; search prose never becomes an untracked fact."""

from app.providers.alternatives import NormalizedProviderItem, ProviderItemKind
from app.providers.search import SearchProvider, SearchRequest
from app.planning.provider_support import ProviderSpecialist


class PlacesSpecialist(ProviderSpecialist[tuple]):
    kind = ProviderItemKind.SEARCH

    def run(self, trip_id: str, trip_version: int, request: SearchRequest, provider: SearchProvider | None):
        def normalize(result):
            evidence = {item.id: item for item in result.evidence}
            return tuple(
                NormalizedProviderItem(
                    trip_id=trip_id,
                    trip_version=trip_version,
                    kind=self.kind,
                    provider=provider.name,
                    provider_item_id=hit.reference_url,
                    title=hit.title,
                    detail=hit.snippet,
                    reference_url=hit.reference_url,
                    retrieved_at=min(evidence[item].retrieved_at for item in hit.evidence_ids),
                    expires_at=min((evidence[item].expires_at for item in hit.evidence_ids if evidence[item].expires_at), default=None),
                    evidence=tuple(evidence[item] for item in hit.evidence_ids),
                )
                for hit in result.value
            )
        return self.execute(trip_id, trip_version, request, provider, lambda: provider.search(request), normalize)
