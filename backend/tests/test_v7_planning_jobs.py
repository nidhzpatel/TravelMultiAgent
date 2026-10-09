from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pydantic import BaseModel, ConfigDict

from app.domain.contracts import Budget, Money, PriceStatus, Provenance, Trip, TripBrief
from app.llm import BoundedStructuredModel, ModelBudgetExceeded, ModelSchemaError, StructuredModelResult
from app.persistence.job_repository import JobBaseVersionError, JobCancelledError, SqlAlchemyPlanningJobRepository, StaleFenceError
from app.persistence.repositories import SqlAlchemyTripRepository
from app.planning.jobs import PlanningCandidate, PlanningJobRequest, PlanningJobStatus
from app.planning.orchestrator import BoundedPlanningOrchestrator, SpecialistResult
from app.workers.planning import PlanningWorker


class ModelCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str


class PlanningJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.trips = SqlAlchemyTripRepository("sqlite:///:memory:")
        self.trips.create_schema_for_test()
        self.jobs = SqlAlchemyPlanningJobRepository("", engine=self.trips.engine)
        self.trip = Trip(owner_id="user", title="Goa", brief=TripBrief(origin="Ahmedabad", destination_text="Goa", start_date=datetime(2027, 1, 1).date(), end_date=datetime(2027, 1, 3).date()), budget=Budget(target=Money(amount=Decimal("1000"), currency="USD", status=PriceStatus.USER_PROVIDED, provenance=Provenance.USER)))
        self.trips.create(self.trip)
        self.now = datetime(2026, 10, 9, tzinfo=timezone.utc)

    def request(self, key: str = "planning-job-key-0001", **updates) -> PlanningJobRequest:
        return PlanningJobRequest(idempotency_key=key, **updates)

    def test_job_survives_repository_restart_and_is_idempotent(self) -> None:
        with TemporaryDirectory() as directory:
            database_url = f"sqlite:///{Path(directory) / 'jobs.db'}"
            trips = SqlAlchemyTripRepository(database_url)
            trips.create_schema_for_test()
            trips.create(self.trip)
            first = SqlAlchemyPlanningJobRepository(database_url)
            created = first.create(self.trip.id, "user", 1, self.request(), self.now)
            restarted = SqlAlchemyPlanningJobRepository(database_url)
            self.assertEqual(restarted.get(created.id), created)
            self.assertEqual(restarted.create(self.trip.id, "user", 1, self.request(), self.now).id, created.id)
            with self.assertRaises(ValueError):
                restarted.create(self.trip.id, "user", 1, self.request(deadline_seconds=60), self.now)

    def test_worker_termination_reclaims_lease_and_stale_fence_cannot_write(self) -> None:
        created = self.jobs.create(self.trip.id, "user", 1, self.request(), self.now)
        first = self.jobs.claim_next("worker-1", lease_seconds=10, now=self.now)
        second = self.jobs.claim_next("worker-2", lease_seconds=10, now=self.now + timedelta(seconds=11))
        self.assertEqual(second.fencing_token, first.fencing_token + 1)
        with self.assertRaises(StaleFenceError):
            self.jobs.checkpoint(created.id, "worker-1", first.fencing_token, "late write", 50, now=self.now + timedelta(seconds=11))
        candidate = PlanningCandidate(trip=self.trip.model_copy(update={"title": "Reclaimed draft"}))
        committed = self.jobs.commit_candidate(created.id, "worker-2", second.fencing_token, candidate, now=self.now + timedelta(seconds=12))
        self.assertEqual(committed.status, PlanningJobStatus.SUCCEEDED)
        self.assertEqual(self.trips.get(self.trip.id).trip.title, "Reclaimed draft")

    def test_cancellation_retry_deadline_and_events_are_terminal(self) -> None:
        cancelled = self.jobs.create(self.trip.id, "user", 1, self.request("planning-job-key-0002"), self.now)
        self.assertEqual(self.jobs.request_cancel(cancelled.id, self.now).status, PlanningJobStatus.CANCELLED)

        running = self.jobs.create(self.trip.id, "user", 1, self.request("planning-job-key-0003"), self.now)
        lease = self.jobs.claim_next("worker", now=self.now)
        self.jobs.request_cancel(running.id, self.now + timedelta(seconds=1))
        with self.assertRaises(JobCancelledError):
            self.jobs.checkpoint(running.id, "worker", lease.fencing_token, "should stop", 50, now=self.now + timedelta(seconds=1))
        self.assertEqual(self.jobs.acknowledge_cancellation(running.id, "worker", lease.fencing_token, self.now + timedelta(seconds=1)).status, PlanningJobStatus.CANCELLED)

        retrying = self.jobs.create(self.trip.id, "user", 1, self.request("planning-job-key-0004", max_attempts=2), self.now)
        first = self.jobs.claim_next("worker", now=self.now)
        waiting = self.jobs.retry(retrying.id, "worker", first.fencing_token, "rate_limit", 2, self.now)
        self.assertEqual(waiting.status, PlanningJobStatus.RETRY_WAIT)
        self.assertIsNone(self.jobs.claim_next("worker", now=self.now + timedelta(seconds=1)))
        second = self.jobs.claim_next("worker", now=self.now + timedelta(seconds=3))
        failed = self.jobs.retry(retrying.id, "worker", second.fencing_token, "rate_limit", 2, self.now + timedelta(seconds=3))
        self.assertEqual(failed.status, PlanningJobStatus.FAILED)

        expiring = self.jobs.create(self.trip.id, "user", 1, self.request("planning-job-key-0005", deadline_seconds=5), self.now)
        self.assertIsNone(self.jobs.claim_next("worker", now=self.now + timedelta(seconds=6)))
        self.assertEqual(self.jobs.get(expiring.id).status, PlanningJobStatus.EXPIRED)
        self.assertEqual(self.jobs.events(expiring.id)[-1].event_type, "expired")

    def test_no_commit_after_base_version_change(self) -> None:
        job = self.jobs.create(self.trip.id, "user", 1, self.request(), self.now)
        lease = self.jobs.claim_next("worker", now=self.now)
        self.trips.append_version(self.trip.model_copy(update={"title": "Manual edit"}), expected_version=1)
        with self.assertRaises(JobBaseVersionError):
            self.jobs.commit_candidate(job.id, "worker", lease.fencing_token, PlanningCandidate(trip=self.trip), now=self.now + timedelta(seconds=1))
        self.assertEqual(self.trips.get(self.trip.id).version, 2)

    def test_worker_returns_accepted_draft_needs_input_and_budget_failure(self) -> None:
        job = self.jobs.create(self.trip.id, "user", 1, self.request(), datetime.now(timezone.utc))
        succeeded = PlanningWorker(self.jobs, "worker").run_once()
        self.assertEqual((succeeded.id, succeeded.status, succeeded.result_version), (job.id, PlanningJobStatus.SUCCEEDED, 2))

        incomplete = Trip(owner_id="user", title="Incomplete", brief=TripBrief(destination_text="Goa"), budget=self.trip.budget)
        self.trips.create(incomplete)
        self.jobs.create(incomplete.id, "user", 1, self.request("planning-job-key-0006"), datetime.now(timezone.utc))
        needs_input = PlanningWorker(self.jobs, "worker").run_once()
        self.assertEqual(needs_input.status, PlanningJobStatus.NEEDS_INPUT)

        class Expensive:
            def run(self, _trip):
                return SpecialistResult(specialist="expensive", tokens_used=101, cost_usd=Decimal("0"))
        budget_trip = self.trip.model_copy(update={"id": "trip_" + "b" * 32})
        self.trips.create(budget_trip)
        self.jobs.create(budget_trip.id, "user", 1, self.request("planning-job-key-0007", token_budget=100), datetime.now(timezone.utc))
        failed = PlanningWorker(self.jobs, "worker", BoundedPlanningOrchestrator((Expensive(),))).run_once()
        self.assertEqual((failed.status, failed.error_code), (PlanningJobStatus.FAILED, "model_budget_exceeded"))

    def test_invalid_model_schema_rate_limit_fallback_and_call_budget(self) -> None:
        invalid = BoundedStructuredModel(lambda _prompt: StructuredModelResult(payload={"wrong": True}, tokens_used=1, cost_usd=Decimal("0")))
        with self.assertRaises(ModelSchemaError):
            invalid.invoke("plan", ModelCandidate, 10, Decimal("1"))

        calls = []
        def primary(_prompt):
            calls.append("primary")
            raise RuntimeError("429 rate limit")
        def fallback(_prompt):
            calls.append("fallback")
            return StructuredModelResult(payload={"title": "Fallback"}, tokens_used=5, cost_usd=Decimal("0.1"))
        model = BoundedStructuredModel(primary, fallback)
        result, tokens, cost = model.invoke("plan", ModelCandidate, 10, Decimal("1"))
        self.assertEqual((result.title, tokens, cost, calls), ("Fallback", 5, Decimal("0.1"), ["primary", "fallback"]))
        with self.assertRaises(ModelBudgetExceeded):
            model.invoke("plan", ModelCandidate, 4, Decimal("1"))

    def test_critic_is_advisory_and_specialists_emit_heartbeat_progress(self) -> None:
        class Specialist:
            def run(self, _trip):
                return SpecialistResult(
                    specialist="typed",
                    candidate_facts={"validated": True},
                    candidate_trip=_trip.model_copy(update={"title": "Typed specialist draft"}),
                )

        orchestrator = BoundedPlanningOrchestrator(
            (Specialist(),),
            critic=lambda _trip, _results: ("Review hotel evidence before booking",),
        )
        progress = []
        candidate, _, _ = orchestrator.plan(self.trip, lambda name, index, total: progress.append((name, index, total)))
        self.assertEqual(progress, [("Specialist", 1, 1)])
        self.assertEqual(candidate.advisory_notes, ("Review hotel evidence before booking",))
        self.assertEqual(candidate.trip.title, "Typed specialist draft")
        self.assertEqual(candidate.trip.readiness.value, "ACTION_REQUIRED")

    def test_legacy_crew_factories_are_request_local_without_parser_context(self) -> None:
        from app.crew.crew import build_stay_crew

        first = build_stay_crew()
        second = build_stay_crew()
        self.assertIsNot(first.agents[0], second.agents[0])
        self.assertIsNot(first.tasks[0], second.tasks[0])
        self.assertEqual(first.tasks[0].context, [])
        self.assertEqual(second.tasks[0].context, [])

    def test_v2_planning_path_does_not_depend_on_swarm_or_legacy_main(self) -> None:
        root = Path(__file__).parents[1] / "app"
        for path in (
            root / "workers" / "planning.py",
            root / "planning" / "orchestrator.py",
            root / "api" / "v2" / "planning_jobs.py",
        ):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("app.swarm", source)
            self.assertNotIn("app.main", source)


if __name__ == "__main__":
    unittest.main()
