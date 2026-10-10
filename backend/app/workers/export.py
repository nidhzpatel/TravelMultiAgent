"""Version-pinned trip export boundary used by HTTP and background workers."""

from __future__ import annotations

from app.exports.trip_pdf import render_trip_pdf
from app.persistence.repositories import SqlAlchemyTripRepository
from app.planning.budget import build_budget_breakdown


class VersionedExportWorker:
    """Render immutable accepted trip versions without reading pending proposals."""

    def __init__(self, repository: SqlAlchemyTripRepository) -> None:
        self._repository = repository

    def render_pdf(self, trip_id: str, version: int) -> bytes | None:
        trip = self._repository.get_version(trip_id, version)
        if trip is None:
            return None
        return render_trip_pdf(
            trip,
            build_budget_breakdown(trip.trip.budget),
            self._repository.list_provider_items(trip_id, version),
            self._repository.list_provider_runs(trip_id, version),
        )
