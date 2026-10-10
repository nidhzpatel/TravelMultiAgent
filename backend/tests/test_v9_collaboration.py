import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v2.collaboration import router as collaboration_router
from app.api.v2.trips import get_repository, router as trips_router
from app.persistence.repositories import SqlAlchemyTripRepository
from app.security.identity import Principal, current_principal


class CollaborationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        self.repository.create_schema_for_test()
        app = FastAPI()
        app.include_router(trips_router)
        app.include_router(collaboration_router)
        app.dependency_overrides[get_repository] = lambda: self.repository
        app.dependency_overrides[current_principal] = lambda: Principal(subject="owner")
        self.app = app
        self.client = TestClient(app)
        created = self.client.post("/v2/trips", json={"title": "Shared trip", "brief": {"destination_text": "Goa"}, "budget": {"target": {"amount": "1000", "currency": "USD", "status": "USER_PROVIDED", "provenance": "USER"}}})
        self.trip_id = created.json()["trip_id"]

    def test_share_accept_revoke_member_and_cross_user_denial(self) -> None:
        created = self.client.post(f"/v2/trips/{self.trip_id}/shares", json={"role": "EDITOR", "expires_in_hours": 24})
        self.assertEqual(created.status_code, 201)
        token = created.json()["token"]
        share_id = created.json()["invitation"]["id"]

        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="editor")
        accepted = self.client.post(f"/v2/shares/{token}/accept")
        self.assertEqual(accepted.json(), {"trip_id": self.trip_id, "role": "EDITOR"})
        self.assertEqual(self.client.get(f"/v2/trips/{self.trip_id}").status_code, 200)
        self.assertEqual(self.client.get(f"/v2/trips/{self.trip_id}/members").status_code, 404)

        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="owner")
        members = self.client.get(f"/v2/trips/{self.trip_id}/members").json()
        self.assertEqual({(item["user_id"], item["role"]) for item in members}, {("owner", "OWNER"), ("editor", "EDITOR")})
        self.assertEqual(self.client.delete(f"/v2/trips/{self.trip_id}/members/owner").status_code, 409)

        revoked = self.client.delete(f"/v2/trips/{self.trip_id}/shares/{share_id}")
        self.assertIsNotNone(revoked.json()["revoked_at"])
        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="editor")
        self.assertEqual(self.client.get(f"/v2/trips/{self.trip_id}").status_code, 404)

        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="owner")
        second = self.client.post(f"/v2/trips/{self.trip_id}/shares", json={"role": "VIEWER"}).json()
        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="viewer")
        self.client.post(f"/v2/shares/{second['token']}/accept")
        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="owner")
        self.assertEqual(self.client.delete(f"/v2/trips/{self.trip_id}/members/viewer").status_code, 204)

    def test_revoked_and_cross_trip_share_use_are_denied(self) -> None:
        created = self.client.post(f"/v2/trips/{self.trip_id}/shares", json={"role": "VIEWER"}).json()
        self.client.delete(f"/v2/trips/{self.trip_id}/shares/{created['invitation']['id']}")
        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="viewer")
        self.assertEqual(self.client.post(f"/v2/shares/{created['token']}/accept").status_code, 410)
        self.assertEqual(self.client.get(f"/v2/trips/{self.trip_id}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
