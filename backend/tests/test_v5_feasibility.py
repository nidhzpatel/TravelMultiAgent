from datetime import date, datetime, timedelta
from decimal import Decimal
import unittest
from zoneinfo import ZoneInfo

from app.planning.scheduler import OpeningWindow, PlannedDay, PlannedItem, schedule_after
from app.providers.places import ResolvedPlace
from app.providers.routes import RouteCache, RouteRequest, RouteResult, RouteStatus
from app.validation.geography import validate_radius
from app.validation.timeline import timeline_is_action_ready, validate_timeline


class FeasibilityPlannerTests(unittest.TestCase):
    def item(self, place: str, start: datetime, minutes: int = 60, kind: str = "activity", windows=()) -> PlannedItem:
        return PlannedItem(kind=kind, entity_id="activity_" + "a" * 32, place_id=place, start_at=start, end_at=start + timedelta(minutes=minutes), opening_windows=windows)

    def route(self, origin: str, destination: str, status: RouteStatus = RouteStatus.REACHABLE, minutes: int | None = 30) -> RouteResult:
        return RouteResult(origin_place_id=origin, destination_place_id=destination, mode="drive", status=status, duration_minutes=minutes)

    def test_routes_are_directed_and_cache_expires(self) -> None:
        zone = ZoneInfo("Asia/Kolkata")
        request = RouteRequest(origin_place_id="a", destination_place_id="b", depart_at=datetime(2026, 1, 1, 9, tzinfo=zone))
        reverse = request.model_copy(update={"origin_place_id": "b", "destination_place_id": "a"})
        result = self.route("a", "b")
        cache = RouteCache()
        cache.put(request, result, timedelta(minutes=10))
        self.assertEqual(cache.get(request), result.model_copy(update={"expires_at": result.retrieved_at + timedelta(minutes=10)}))
        self.assertIsNone(cache.get(reverse))
        self.assertIsNone(cache.get(request, result.retrieved_at + timedelta(minutes=11)))

    def test_unknown_and_unreachable_routes_are_explicit_and_block_ready(self) -> None:
        zone = ZoneInfo("Asia/Kolkata")
        first = self.item("a", datetime(2026, 1, 1, 9, tzinfo=zone))
        second = self.item("b", datetime(2026, 1, 1, 11, tzinfo=zone))
        day = PlannedDay(local_date=date(2026, 1, 1), timezone="Asia/Kolkata", items=(first, second))
        unknown = self.route("a", "b", RouteStatus.UNKNOWN, None)
        unreachable = self.route("a", "b", RouteStatus.UNREACHABLE, None)
        self.assertIn("unknown", validate_timeline(day, (unknown,))[0].message.lower())
        self.assertIn("unreachable", validate_timeline(day, (unreachable,))[0].message.lower())
        self.assertFalse(timeline_is_action_ready((day,), (unknown,)))

    def test_scheduler_respects_route_buffer_and_opening_window(self) -> None:
        zone = ZoneInfo("Europe/Paris")
        first = self.item("a", datetime(2026, 3, 29, 8, tzinfo=zone))
        window = OpeningWindow(opens_at=datetime(2026, 3, 29, 10, tzinfo=zone), closes_at=datetime(2026, 3, 29, 18, tzinfo=zone))
        second = self.item("b", datetime(2026, 3, 29, 9, tzinfo=zone), windows=(window,))
        scheduled = schedule_after(first, second, self.route("a", "b", minutes=45), buffer_minutes=15)
        self.assertEqual(scheduled.start_at, datetime(2026, 3, 29, 10, tzinfo=zone))

    def test_overnight_transport_and_hotel_spans_are_valid(self) -> None:
        zone = ZoneInfo("Asia/Kolkata")
        transport = self.item("a", datetime(2026, 1, 1, 23, tzinfo=zone), minutes=180, kind="transport")
        hotel = self.item("a", datetime(2026, 1, 2, 14, tzinfo=zone), minutes=16 * 60, kind="hotel")
        day = PlannedDay(local_date=date(2026, 1, 1), timezone="Asia/Kolkata", items=(transport,))
        self.assertEqual(validate_timeline(day, ()), ())
        self.assertGreater(hotel.end_at, hotel.start_at)

    def test_radius_policy_uses_coordinates_without_inventing_routes(self) -> None:
        anchor = ResolvedPlace(name="Goa", provider_place_id="goa", latitude=Decimal("15.49"), longitude=Decimal("73.82"), timezone="Asia/Kolkata")
        nearby = ResolvedPlace(name="Panaji", provider_place_id="panaji", latitude=Decimal("15.50"), longitude=Decimal("73.83"), timezone="Asia/Kolkata")
        far = ResolvedPlace(name="Mumbai", provider_place_id="mumbai", latitude=Decimal("19.07"), longitude=Decimal("72.87"), timezone="Asia/Kolkata")
        self.assertEqual(validate_radius(anchor, (nearby,), Decimal("50")), ())
        self.assertEqual(validate_radius(anchor, (far,), Decimal("50"))[0].rule, "radius")


if __name__ == "__main__":
    unittest.main()
