from pathlib import Path
from decimal import Decimal
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v2.trips import get_repository, router
from app.persistence.repositories import SqlAlchemyTripRepository
from app.security.identity import Principal, current_principal


ROOT = Path(__file__).parents[2]


class WorkspaceExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        self.repository.create_schema_for_test()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_repository] = lambda: self.repository
        app.dependency_overrides[current_principal] = lambda: Principal(subject="owner")
        self.app = app
        self.client = TestClient(app)
        created = self.client.post("/v2/trips", json={"title": "Accepted Goa", "brief": {"origin": "Ahmedabad", "destination_text": "Goa", "start_date": "2027-01-01", "end_date": "2027-01-03"}, "budget": {"target": {"amount": "1000", "currency": "USD", "status": "USER_PROVIDED", "provenance": "USER"}}})
        self.trip_id = created.json()["trip_id"]

    def test_pdf_is_version_pinned_and_excludes_pending_preview(self) -> None:
        preview = self.client.post(f"/v2/trips/{self.trip_id}/proposals", json={"expected_version": 1, "idempotency_key": "workspace-preview-0001", "operations": [{"kind": "REPLACE", "path": "title", "value": "Pending Kerala"}]})
        self.assertEqual(preview.status_code, 200)
        version_one = self.client.get(f"/v2/trips/{self.trip_id}/export.pdf?version=1")
        self.assertEqual((version_one.status_code, version_one.headers["content-type"]), (200, "application/pdf"))
        self.assertIn(b"Accepted Goa", version_one.content)
        self.assertIn(b"Accepted trip version: 1", version_one.content)
        self.assertIn(b"Pending previews are excluded", version_one.content)
        self.assertNotIn(b"Pending Kerala", version_one.content)

        committed = self.client.post(f"/v2/trips/{self.trip_id}/proposals/{preview.json()['proposal_id']}/commit")
        self.assertEqual(committed.json()["version"], 2)
        version_two = self.client.get(f"/v2/trips/{self.trip_id}/export.pdf?version=2")
        self.assertIn(b"Pending Kerala", version_two.content)
        self.assertIn(b"Provider status: no version-pinned provider runs", version_two.content)
        self.assertIn(b"No retained source evidence", version_two.content)
        self.assertIn(b"Accepted Goa", self.client.get(f"/v2/trips/{self.trip_id}/export.pdf?version=1").content)
        accepted_v2 = self.repository.get(self.trip_id)
        assert accepted_v2 is not None
        changed_target = accepted_v2.trip.budget.target.model_copy(update={"amount": Decimal("2000")})
        changed_budget = accepted_v2.trip.budget.model_copy(update={"target": changed_target})
        self.repository.append_version(accepted_v2.trip.model_copy(update={"budget": changed_budget}), expected_version=2)
        self.assertEqual(Decimal(self.client.get(f"/v2/trips/{self.trip_id}/budget?version=1").json()["target"]["amount"]), Decimal("1000"))
        self.assertEqual(Decimal(self.client.get(f"/v2/trips/{self.trip_id}/budget?version=3").json()["target"]["amount"]), Decimal("2000"))

    def test_pdf_export_is_member_scoped(self) -> None:
        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="stranger")
        self.assertEqual(self.client.get(f"/v2/trips/{self.trip_id}/export.pdf?version=1").status_code, 404)

    def test_frontend_keeps_canonical_and_pending_state_separate(self) -> None:
        workspace = (ROOT / "frontend/src/components/V2ProposalWorkspace.tsx").read_text()
        conversation = (ROOT / "frontend/src/features/trips/TripConversation.tsx").read_text()
        api = (ROOT / "frontend/src/api.ts").read_text()
        self.assertIn("xl:grid-cols-[20rem_minmax(0,1fr)_22rem]", workspace)
        self.assertIn("Pending change", (ROOT / "frontend/src/components/ChangePreview.tsx").read_text())
        self.assertIn("reason instanceof ApiError && reason.status === 409", conversation)
        self.assertIn("await onConflict()", conversation)
        self.assertIn("export.pdf?version=${version}", api)
        self.assertIn("budget?version=${version}", api)
        self.assertIn("useReducedMotion", (ROOT / "frontend/src/components/ChangePreview.tsx").read_text())


if __name__ == "__main__":
    unittest.main()
