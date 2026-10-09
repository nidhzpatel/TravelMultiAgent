from datetime import date
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v2.providers import get_provider_registry, router as provider_router
from app.api.v2.trips import get_repository, router as trip_router
from app.config import Settings
from app.persistence.repositories import SqlAlchemyTripRepository
from app.providers.registry import build_provider_registry
from app.security.identity import Principal, current_principal


class ProviderApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        self.repository.create_schema_for_test()
        app = FastAPI()
        app.include_router(trip_router)
        app.include_router(provider_router)
        app.dependency_overrides[get_repository] = lambda: self.repository
        app.dependency_overrides[current_principal] = lambda: Principal(subject="user_alice")
        app.dependency_overrides[get_provider_registry] = lambda: build_provider_registry(Settings(environment="development"))
        self.app = app
        self.client = TestClient(app)

    def create_trip(self) -> str:
        response = self.client.post("/v2/trips", json={"title": "Goa", "brief": {"destination_text": "Goa"}, "budget": {"target": {"amount": "1000", "currency": "USD", "status": "USER_PROVIDED", "provenance": "USER"}}})
        self.assertEqual(response.status_code, 201)
        return response.json()["trip_id"]

    def test_refresh_persists_versioned_mock_labeled_results_and_owner_scope(self) -> None:
        trip_id = self.create_trip()
        request = {
            "search": {"query": "Goa beaches", "market": "IN"},
            "weather": {"place_id": "goa", "latitude": "15.49", "longitude": "73.82", "start_date": date.today().isoformat(), "end_date": date.today().isoformat()},
        }
        refreshed = self.client.post(f"/v2/trips/{trip_id}/provider-data/refresh", json=request)
        self.assertEqual(refreshed.status_code, 200)
        self.assertEqual({item["kind"] for item in refreshed.json()["items"]}, {"SEARCH", "WEATHER"})
        self.assertTrue(all(item["evidence"][0]["provenance"] == "MOCK" for item in refreshed.json()["items"]))
        self.assertTrue(all(run["status"] == "MOCK" for run in refreshed.json()["outcomes"]))
        self.assertEqual(self.client.get(f"/v2/trips/{trip_id}/provider-data?version=1").json(), refreshed.json())

        self.repository.set_member_role(trip_id, "user_bob", "VIEWER")
        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="user_bob")
        self.assertEqual(self.client.get(f"/v2/trips/{trip_id}/provider-data").status_code, 200)
        self.assertEqual(self.client.post(f"/v2/trips/{trip_id}/provider-data/refresh", json=request).status_code, 403)

    def test_provider_data_rejects_unknown_trip_and_version(self) -> None:
        trip_id = self.create_trip()
        self.assertEqual(self.client.get(f"/v2/trips/{trip_id}/provider-data?version=99").status_code, 404)
        self.assertEqual(self.client.get("/v2/trips/trip_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/provider-data").status_code, 404)


if __name__ == "__main__":
    unittest.main()
