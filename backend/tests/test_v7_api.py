import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v2.planning_jobs import router as jobs_router
from app.api.v2.trips import get_repository, router as trips_router
from app.persistence.job_repository import SqlAlchemyPlanningJobRepository
from app.persistence.repositories import SqlAlchemyTripRepository
from app.security.identity import Principal, current_principal
from app.workers.planning import PlanningWorker


class PlanningJobApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = SqlAlchemyTripRepository("sqlite:///:memory:")
        self.repository.create_schema_for_test()
        app = FastAPI()
        app.include_router(trips_router)
        app.include_router(jobs_router)
        app.dependency_overrides[get_repository] = lambda: self.repository
        app.dependency_overrides[current_principal] = lambda: Principal(subject="user")
        self.app = app
        self.client = TestClient(app)
        response = self.client.post("/v2/trips", json={"title": "Goa", "brief": {"origin": "Ahmedabad", "destination_text": "Goa", "start_date": "2027-01-01", "end_date": "2027-01-03"}, "budget": {"target": {"amount": "1000", "currency": "USD", "status": "USER_PROVIDED", "provenance": "USER"}}})
        self.trip_id = response.json()["trip_id"]

    def test_create_is_nonblocking_idempotent_and_exposes_progress(self) -> None:
        payload = {"idempotency_key": "planning-api-job-0001", "deadline_seconds": 60}
        created = self.client.post(f"/v2/trips/{self.trip_id}/planning-jobs", json=payload)
        self.assertEqual(created.status_code, 202)
        self.assertEqual(created.json()["status"], "QUEUED")
        replay = self.client.post(f"/v2/trips/{self.trip_id}/planning-jobs", json=payload)
        self.assertEqual(replay.json()["id"], created.json()["id"])
        job_id = created.json()["id"]
        self.assertEqual(self.client.get(f"/v2/trips/{self.trip_id}/planning-jobs/{job_id}").status_code, 200)
        events = self.client.get(f"/v2/trips/{self.trip_id}/planning-jobs/{job_id}/events").json()
        self.assertEqual(events[0]["event_type"], "queued")
        self.assertEqual(self.client.post(f"/v2/trips/{self.trip_id}/planning-jobs/{job_id}/cancel").json()["status"], "CANCELLED")

    def test_viewer_can_read_but_cannot_start_or_cancel(self) -> None:
        job = self.client.post(f"/v2/trips/{self.trip_id}/planning-jobs", json={"idempotency_key": "planning-api-job-0002"}).json()
        self.repository.set_member_role(self.trip_id, "viewer", "VIEWER")
        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="viewer")
        self.assertEqual(self.client.get(f"/v2/trips/{self.trip_id}/planning-jobs/{job['id']}").status_code, 200)
        self.assertEqual(self.client.post(f"/v2/trips/{self.trip_id}/planning-jobs", json={"idempotency_key": "planning-api-job-0003"}).status_code, 403)
        self.assertEqual(self.client.post(f"/v2/trips/{self.trip_id}/planning-jobs/{job['id']}/cancel").status_code, 403)

    def test_editor_can_enqueue_and_worker_commits_without_changing_owner(self) -> None:
        self.repository.set_member_role(self.trip_id, "editor", "EDITOR")
        self.app.dependency_overrides[current_principal] = lambda: Principal(subject="editor")
        created = self.client.post(
            f"/v2/trips/{self.trip_id}/planning-jobs",
            json={"idempotency_key": "planning-editor-job-0001"},
        )
        self.assertEqual(created.status_code, 202)
        jobs = SqlAlchemyPlanningJobRepository("", engine=self.repository.engine)
        result = PlanningWorker(jobs, "worker").run_once()
        self.assertEqual(result.status.value, "SUCCEEDED")
        accepted = self.repository.get(self.trip_id)
        self.assertEqual((accepted.version, accepted.trip.owner_id), (2, "user"))


if __name__ == "__main__":
    unittest.main()
