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
        self.app = app
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
        proposal = {"expected_version": 1, "idempotency_key": "proposal-replace-title-0001", "operations": [{"kind": "REPLACE", "path": "title", "value": "Revised Goa"}]}
        preview = self.client.post(f"/v2/trips/{trip_id}/proposals", json=proposal)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["preview"]["title"], "Revised Goa")
        self.assertEqual(preview.json()["changed_fields"], ["title"])
        self.assertEqual(preview.json()["changes"], [{"entity_id": trip_id, "fields": ["title"]}])
        proposal_id = preview.json()["proposal_id"]
        replay = self.client.post(f"/v2/trips/{trip_id}/proposals", json=proposal)
        self.assertEqual(replay.json(), preview.json())
        changed_replay = {**proposal, "operations": [{"kind": "REPLACE", "path": "title", "value": "Different"}]}
        self.assertEqual(self.client.post(f"/v2/trips/{trip_id}/proposals", json=changed_replay).status_code, 409)
        committed_by_id = self.client.post(f"/v2/trips/{trip_id}/proposals/{proposal_id}/commit")
        self.assertEqual(committed_by_id.status_code, 200)
        self.assertEqual(committed_by_id.json()["version"], 2)
        self.assertEqual(self.client.post(f"/v2/trips/{trip_id}/proposals/{proposal_id}/commit").json()["version"], 2)
        self.assertEqual(self.client.post(f"/v2/trips/{trip_id}/proposals/commit", json=proposal).status_code, 404)
        question = self.client.post(f"/v2/trips/{trip_id}/messages", json={"message": "When is my flight?", "idempotency_key": "message-read-only-0001"})
        self.assertEqual(question.json()["status"], "read")
        self.assertEqual(self.repository.get(trip_id).version, 2)

    def test_ambiguity_stale_base_and_competing_edits_preserve_state(self) -> None:
        created = self.client.post("/v2/trips", json=self._payload()).json()
        trip_id = created["trip_id"]
        ambiguity = self.client.post(f"/v2/trips/{trip_id}/messages", json={"message": "change my second hotel", "idempotency_key": "ambiguous-hotel-0001"})
        self.assertEqual(ambiguity.json()["status"], "clarifying")
        self.assertEqual(self.repository.get(trip_id).version, 1)

        first = {"expected_version": 1, "idempotency_key": "competing-edit-key-0001", "operations": [{"kind": "REPLACE", "path": "title", "value": "First edit"}]}
        second = {"expected_version": 1, "idempotency_key": "competing-edit-key-0002", "operations": [{"kind": "REPLACE", "path": "title", "value": "Second edit"}]}
        first_preview = self.client.post(f"/v2/trips/{trip_id}/proposals", json=first).json()
        second_preview = self.client.post(f"/v2/trips/{trip_id}/proposals", json=second).json()
        self.assertEqual(self.client.post(f"/v2/trips/{trip_id}/proposals/{first_preview['proposal_id']}/commit").status_code, 200)
        self.assertEqual(self.client.post(f"/v2/trips/{trip_id}/proposals/{second_preview['proposal_id']}/commit").status_code, 409)
        current = self.repository.get(trip_id)
        self.assertEqual(current.version, 2)
        self.assertEqual(current.trip.title, "First edit")

        stale = {"expected_version": 1, "idempotency_key": "stale-edit-key-00001", "operations": [{"kind": "REPLACE", "path": "title", "value": "Stale edit"}]}
        self.assertEqual(self.client.post(f"/v2/trips/{trip_id}/proposals", json=stale).status_code, 409)
        self.assertEqual(self.repository.get(trip_id), current)

    def test_read_operation_commit_creates_no_version(self) -> None:
        trip_id = self.client.post("/v2/trips", json=self._payload()).json()["trip_id"]
        request = {"expected_version": 1, "idempotency_key": "typed-read-key-00001", "operations": [{"kind": "READ", "path": "title"}]}
        proposal = self.client.post(f"/v2/trips/{trip_id}/proposals", json=request)
        self.assertEqual(proposal.status_code, 200)
        committed = self.client.post(f"/v2/trips/{trip_id}/proposals/{proposal.json()['proposal_id']}/commit")
        self.assertEqual(committed.status_code, 200)
        self.assertEqual(committed.json()["version"], 1)
        self.assertIsNone(self.repository.get_version(trip_id, 2))

    def test_budget_endpoint_and_export_share_the_canonical_ledger(self) -> None:
        payload = self._payload()
        payload["budget"]["expenses"] = [
            {
                "category": "hotel",
                "money": {"amount": "1200", "currency": "USD", "status": "ESTIMATED", "provenance": "LIVE"},
                "quantity": "2",
                "unit": "night",
            },
            {
                "category": "transport",
                "money": {"amount": None, "currency": "USD", "status": "UNKNOWN", "provenance": "LIVE"},
                "mandatory": True,
            },
        ]
        created = self.client.post("/v2/trips", json=payload)
        self.assertEqual(created.status_code, 201)
        trip_id = created.json()["trip_id"]
        budget = self.client.get(f"/v2/trips/{trip_id}/budget")
        exported = self.client.get(f"/v2/trips/{trip_id}/export")
        pdf = self.client.get(f"/v2/trips/{trip_id}/budget.pdf")
        self.assertEqual(budget.status_code, 200)
        self.assertEqual(budget.json()["breakdown"]["known_total"], "2400.00")
        self.assertEqual(budget.json()["breakdown"]["feasibility"], "UNKNOWN")
        self.assertEqual(budget.json()["expenses"], exported.json()["trip"]["budget"]["expenses"])
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertIn(b"Known total: USD 2400.00", pdf.content)
        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="user_bob")
        self.assertEqual(self.client.get(f"/v2/trips/{trip_id}/budget").status_code, 404)
        self.assertEqual(self.client.get(f"/v2/trips/{trip_id}/budget.pdf").status_code, 404)


if __name__ == "__main__":
    unittest.main()
