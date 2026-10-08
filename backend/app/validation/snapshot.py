"""Validation of the provider-resolved schedule embedded in a trip snapshot."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.domain.contracts import FactStatus, TransportLeg, Trip, ValidationResult
from app.planning.geography import geodesic_km
from app.providers.places import ResolvedPlace


def validate_trip_snapshot(trip: Trip, at: datetime | None = None) -> tuple[ValidationResult, ...]:
    issues: list[ValidationResult] = []
    now = at or datetime.now(timezone.utc)
    destinations = {destination.id: destination for destination in trip.destinations}
    if trip.destinations:
        anchor = trip.destinations[0]
        if anchor.latitude is None or anchor.longitude is None or anchor.timezone is None:
            issues.append(ValidationResult(rule="geography", severity="error", message="Anchor destination is unresolved", entity_ids=(anchor.id,)))
        else:
            anchor_place = ResolvedPlace(name=anchor.name, provider_place_id=anchor.provider_place_id or anchor.id, latitude=anchor.latitude, longitude=anchor.longitude, timezone=anchor.timezone, evidence_ids=anchor.evidence_ids)
            for destination in trip.destinations[1:]:
                if destination.latitude is None or destination.longitude is None or destination.timezone is None:
                    issues.append(ValidationResult(rule="geography", severity="error", message="Destination is unresolved", entity_ids=(destination.id,)))
                    continue
                place = ResolvedPlace(name=destination.name, provider_place_id=destination.provider_place_id or destination.id, latitude=destination.latitude, longitude=destination.longitude, timezone=destination.timezone, evidence_ids=destination.evidence_ids)
                if geodesic_km(anchor_place, place) > trip.radius_km:
                    issues.append(ValidationResult(rule="radius", severity="error", message=f"Destination exceeds {trip.radius_km} km radius", entity_ids=(destination.id,)))

    routes: dict[tuple[str, str], list[TransportLeg]] = {}
    for route in trip.transport_legs:
        routes.setdefault((route.origin_destination_id, route.destination_destination_id), []).append(route)
    for day in trip.days:
        zone = ZoneInfo(day.timezone)
        for item in day.scheduled_items:
            if item.destination_id not in destinations:
                issues.append(ValidationResult(rule="geography", severity="error", message="Scheduled item destination is unresolved", entity_ids=(item.id,)))
            if item.start_at is None or item.end_at is None:
                if item.critical:
                    issues.append(ValidationResult(rule="timeline", severity="error", message="Critical item time is unknown", entity_ids=(item.id,)))
                continue
            if item.start_at.astimezone(zone).date() != day.local_date and item.kind not in {"transport", "hotel"}:
                issues.append(ValidationResult(rule="local_date", severity="error", message="Item starts outside its trip day", entity_ids=(item.id,)))
            if item.opening_windows and not any(window.opens_at <= item.start_at and item.end_at <= window.closes_at for window in item.opening_windows):
                issues.append(ValidationResult(rule="opening_window", severity="error", message="Item is outside opening hours", entity_ids=(item.id,)))
        for previous, current in zip(day.scheduled_items, day.scheduled_items[1:]):
            if previous.end_at is None or current.start_at is None:
                continue
            duration = 0
            if previous.destination_id != current.destination_id:
                candidates = routes.get((previous.destination_id, current.destination_id), [])
                if len(candidates) != 1:
                    message = "Dynamic route duration is unresolved" if not candidates else "Dynamic route choice is ambiguous"
                    issues.append(ValidationResult(rule="route", severity="error", message=message, entity_ids=(previous.id, current.id)))
                    continue
                route = candidates[0]
                if route.route_status == "UNKNOWN" or route.duration_minutes.status in {FactStatus.UNKNOWN, FactStatus.STALE}:
                    issues.append(ValidationResult(rule="route", severity="error", message="Dynamic route duration is unresolved", entity_ids=(previous.id, current.id)))
                    continue
                if route.route_status == "UNREACHABLE":
                    issues.append(ValidationResult(rule="route", severity="error", message="Dynamic route is unreachable", entity_ids=(previous.id, current.id)))
                    continue
                if route.expires_at is None or route.expires_at <= now:
                    issues.append(ValidationResult(rule="route", severity="error", message="Dynamic route evidence is stale", entity_ids=(previous.id, current.id)))
                    continue
                duration = int(route.duration_minutes.value)
            required = previous.end_at.timestamp() + (duration + current.required_buffer_minutes) * 60
            if current.start_at.timestamp() < required:
                issues.append(ValidationResult(rule="timeline", severity="error", message="Travel time and buffer do not fit", entity_ids=(previous.id, current.id)))
    return tuple(issues)
