from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import unittest
from zoneinfo import ZoneInfo

from app.planning.scheduler import OpeningWindow, PlannedDay, PlannedItem, schedule_after
from app.domain.contracts import Budget, Destination, Fact, FactStatus, Money, PriceStatus, Provenance, ScheduledItem, TransportLeg, Trip, TripBrief, TripDay, TripReadiness
from app.persistence.repositories import SqlAlchemyTripRepository
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

    def test_scheduler_uses_elapsed_time_across_dst_transition(self) -> None:
        zone = ZoneInfo("Europe/Paris")
        first = self.item("a", datetime(2026, 3, 29, 0, 30, tzinfo=zone), minutes=60)
        second = self.item("b", datetime(2026, 3, 29, 1, 45, tzinfo=zone))
        scheduled = schedule_after(first, second, self.route("a", "b", minutes=30), buffer_minutes=0)
        self.assertEqual(scheduled.start_at, datetime(2026, 3, 29, 3, 0, tzinfo=zone))

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

    def test_resolved_dynamic_schedule_persists_and_unknown_route_blocks_ready(self) -> None:
        zone = ZoneInfo("Asia/Kolkata")
        goa = Destination(name="Goa", provider_place_id="goa", latitude=Decimal("15.49"), longitude=Decimal("73.82"), timezone="Asia/Kolkata")
        panaji = Destination(name="Panaji", provider_place_id="panaji", latitude=Decimal("15.50"), longitude=Decimal("73.83"), timezone="Asia/Kolkata")
        first = ScheduledItem(kind="activity", entity_id="activity_" + "a" * 32, destination_id=goa.id, start_at=datetime(2026, 1, 1, 9, tzinfo=zone), end_at=datetime(2026, 1, 1, 10, tzinfo=zone))
        second = ScheduledItem(kind="activity", entity_id="activity_" + "b" * 32, destination_id=panaji.id, start_at=datetime(2026, 1, 1, 11, tzinfo=zone), end_at=datetime(2026, 1, 1, 12, tzinfo=zone))
        day = TripDay(local_date=date(2026, 1, 1), timezone="Asia/Kolkata", scheduled_items=(first, second))
        evidence_id = "evidence_" + "c" * 32
        retrieved_at = datetime.now(timezone.utc)
        route = TransportLeg(origin_destination_id=goa.id, destination_destination_id=panaji.id, mode="cab", route_status="REACHABLE", duration_minutes=Fact(value=30, status=FactStatus.VERIFIED, evidence_ids=(evidence_id,)), source_provider="route-api", retrieved_at=retrieved_at, expires_at=retrieved_at + timedelta(minutes=15), evidence_ids=(evidence_id,))
        budget = Budget(target=Money(amount=Decimal("1000"), currency="USD", status=PriceStatus.USER_PROVIDED, provenance=Provenance.USER))
        trip = Trip(owner_id="user", title="Dynamic Goa", brief=TripBrief(destination_text="Goa"), budget=budget, destinations=(goa, panaji), days=(day,), transport_legs=(route,), readiness=TripReadiness.READY_TO_BOOK)
        repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        repository.create_schema_for_test()
        repository.create(trip)
        self.assertEqual(repository.get(trip.id).trip, trip)
        with self.assertRaises(ValueError):
            Trip(owner_id="user", title="Unknown route", brief=TripBrief(destination_text="Goa"), budget=budget, destinations=(goa, panaji), days=(day,), readiness=TripReadiness.READY_TO_BOOK)
        expired_route = route.model_copy(update={"retrieved_at": retrieved_at - timedelta(hours=2), "expires_at": retrieved_at - timedelta(hours=1)})
        with self.assertRaises(ValueError):
            Trip(owner_id="user", title="Stale route", brief=TripBrief(destination_text="Goa"), budget=budget, destinations=(goa, panaji), days=(day,), transport_legs=(expired_route,), readiness=TripReadiness.READY_TO_BOOK)

    def test_nested_snapshot_generates_stable_ids_before_reference_lists(self) -> None:
        budget = Budget(target=Money(amount=Decimal("1000"), currency="USD", status=PriceStatus.USER_PROVIDED, provenance=Provenance.USER))
        trip = Trip.model_validate({
            "owner_id": "user",
            "title": "Draft snapshot",
            "brief": {"destination_text": "Goa"},
            "budget": budget.model_dump(mode="json"),
            "destinations": [{"name": "Goa", "latitude": "15.49", "longitude": "73.82", "timezone": "Asia/Kolkata"}],
            "days": [{
                "local_date": "2026-01-01",
                "timezone": "Asia/Kolkata",
                "scheduled_items": [{"kind": "activity", "entity_id": "activity_" + "a" * 32}],
            }],
        })
        self.assertEqual(trip.destination_ids, (trip.destinations[0].id,))
        self.assertEqual(trip.day_ids, (trip.days[0].id,))
        self.assertEqual(trip.days[0].scheduled_item_ids, (trip.days[0].scheduled_items[0].id,))


if __name__ == "__main__":
    unittest.main()
