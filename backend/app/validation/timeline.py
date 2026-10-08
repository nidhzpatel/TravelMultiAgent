from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.contracts import ValidationResult
from app.planning.scheduler import PlannedDay
from app.providers.routes import RouteResult, RouteStatus


def validate_timeline(day: PlannedDay, routes: tuple[RouteResult, ...], buffer_minutes: int = 15) -> tuple[ValidationResult, ...]:
    issues: list[ValidationResult] = []
    try:
        zone = ZoneInfo(day.timezone)
    except ZoneInfoNotFoundError:
        return (ValidationResult(rule="timezone", severity="error", message="Day timezone is invalid"),)
    route_index = {(route.origin_place_id, route.destination_place_id): route for route in routes}
    for item in day.items:
        if item.start_at.astimezone(zone).date() != day.local_date and item.kind != "transport":
            issues.append(ValidationResult(rule="local_date", severity="error", message="Item starts outside its local day", entity_ids=(item.id,)))
        if item.opening_windows and not any(window.opens_at <= item.start_at and item.end_at <= window.closes_at for window in item.opening_windows):
            issues.append(ValidationResult(rule="opening_window", severity="error", message="Item is outside opening hours", entity_ids=(item.id,)))
    for previous, current in zip(day.items, day.items[1:]):
        route = route_index.get((previous.place_id, current.place_id))
        if route is None or route.status is RouteStatus.UNKNOWN:
            issues.append(ValidationResult(rule="route", severity="error", message="Route duration is unknown", entity_ids=(previous.id, current.id)))
            continue
        if route.status is RouteStatus.UNREACHABLE:
            issues.append(ValidationResult(rule="route", severity="error", message="Route is unreachable", entity_ids=(previous.id, current.id)))
            continue
        required = previous.end_at.timestamp() + (route.duration_minutes + buffer_minutes) * 60
        if current.start_at.timestamp() < required:
            issues.append(ValidationResult(rule="timeline", severity="error", message="Travel time and buffer do not fit", entity_ids=(previous.id, current.id)))
    return tuple(issues)


def timeline_is_action_ready(days: tuple[PlannedDay, ...], routes: tuple[RouteResult, ...]) -> bool:
    return not any(issue.severity == "error" for day in days for issue in validate_timeline(day, routes))
