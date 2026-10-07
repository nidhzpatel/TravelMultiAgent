from decimal import Decimal
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v2.trips import get_repository, router
from app.persistence.repositories import SqlAlchemyTripRepository
from app.security.identity import Principal, current_principal


class V2ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        self.repository.create_schema_for_test()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_repository] = lambda: self.repository
        app.dependency_overrides[current_principal] = lambda: Principal(subject="user_alice")
        self.client = TestClient(app)
        self.headers = {}

    def _payload(self) -> dict:
        return {
            "title": "Goa",
            "brief": {"destination_text": "Goa"},
            "budget": {"target": {"amount": "900.00", "currency": "USD", "status": "USER_PROVIDED", "provenance": "USER"}},
            "idempotency_key": "v2-create-goa-trip-0001",
        }

    def test_create_list_get_and_version_are_owner_scoped(self) -> None:
        created = self.client.post("/v2/trips", headers=self.headers, json=self._payload())
        self.assertEqual(created.status_code, 201)
        trip_id = created.json()["trip_id"]
        self.assertEqual(self.client.get("/v2/trips", headers=self.headers).json()[0]["trip_id"], trip_id)
        self.assertEqual(self.client.get(f"/v2/trips/{trip_id}", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get(f"/v2/trips/{trip_id}/versions/1", headers=self.headers).status_code, 200)
        self.assertEqual(
            self.client.put(f"/v2/trips/{trip_id}/members/user_bob", json={"role": "VIEWER"}).status_code,
            200,
        )
        self.assertEqual(self.repository.member_role(trip_id, "user_bob"), "VIEWER")


if __name__ == "__main__":
    unittest.main()
