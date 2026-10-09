"""One bounded execution turn for a durable planning job."""

from __future__ import annotations

from app.persistence.job_repository import JobBaseVersionError, JobBudgetError, JobCancelledError, JobDeadlineError, SqlAlchemyPlanningJobRepository, StaleFenceError
from app.persistence.repositories import SqlAlchemyTripRepository
from app.planning.jobs import PlanningJob, PlanningJobStatus
from app.planning.orchestrator import BoundedPlanningOrchestrator, PlanningNeedsInput


class RetryablePlanningError(Exception):
    pass


class PlanningWorker:
    def __init__(self, repository: SqlAlchemyPlanningJobRepository, worker_id: str, orchestrator: BoundedPlanningOrchestrator | None = None, lease_seconds: int = 30) -> None:
        self.repository = repository
        self.worker_id = worker_id
        self.orchestrator = orchestrator or BoundedPlanningOrchestrator()
        self.lease_seconds = lease_seconds
        self.trip_repository = SqlAlchemyTripRepository("", engine=repository.engine)

    def _finish(self, job: PlanningJob, status: PlanningJobStatus, error_code: str, message: str) -> PlanningJob:
        try:
            return self.repository.finish_without_commit(job.id, self.worker_id, job.fencing_token, status, error_code, message)
        except JobCancelledError:
            return self.repository.acknowledge_cancellation(job.id, self.worker_id, job.fencing_token)
        except JobDeadlineError:
            return self.repository.acknowledge_deadline(job.id, self.worker_id, job.fencing_token)
        except StaleFenceError:
            return self.repository.get(job.id) or job

    def run_once(self) -> PlanningJob | None:
        job = self.repository.claim_next(self.worker_id, self.lease_seconds)
        if job is None:
            return None
        fence = job.fencing_token
        try:
            self.repository.checkpoint(job.id, self.worker_id, fence, "validate brief", 15)
            base = self.trip_repository.get_version(job.trip_id, job.base_version)
            if base is None:
                return self._finish(job, PlanningJobStatus.FAILED, "base_version_missing", "Planning base version is unavailable")
            self.repository.checkpoint(job.id, self.worker_id, fence, "run bounded specialists", 45)
            def heartbeat(specialist: str, index: int, total: int) -> None:
                progress = 45 + int((index - 1) * 25 / max(total, 1))
                self.repository.heartbeat(job.id, self.worker_id, fence, self.lease_seconds)
                self.repository.checkpoint(
                    job.id,
                    self.worker_id,
                    fence,
                    f"run specialist {index} of {total}",
                    progress,
                    {"specialist": specialist},
                )

            candidate, tokens, cost = self.orchestrator.plan(base.trip, on_specialist=heartbeat)
            self.repository.record_usage(job.id, self.worker_id, fence, tokens, cost)
            self.repository.checkpoint(job.id, self.worker_id, fence, "deterministic validation", 80)
            return self.repository.commit_candidate(job.id, self.worker_id, fence, candidate)
        except PlanningNeedsInput as exc:
            return self._finish(job, PlanningJobStatus.NEEDS_INPUT, "missing_trip_fields", f"More trip details are required: {', '.join(exc.missing_fields)}")
        except RetryablePlanningError as exc:
            return self.repository.retry(job.id, self.worker_id, fence, "retryable_planning_error", min(2 ** job.attempt_count, 30))
        except JobCancelledError:
            return self.repository.acknowledge_cancellation(job.id, self.worker_id, fence)
        except JobDeadlineError:
            return self.repository.acknowledge_deadline(job.id, self.worker_id, fence)
        except JobBudgetError:
            return self._finish(job, PlanningJobStatus.FAILED, "model_budget_exceeded", "Planning model budget exceeded")
        except JobBaseVersionError:
            return self._finish(job, PlanningJobStatus.FAILED, "base_version_changed", "Trip changed while planning")
        except StaleFenceError:
            return self.repository.get(job.id)
        except Exception:
            return self._finish(job, PlanningJobStatus.FAILED, "invalid_planning_output", "Planning produced an invalid typed result")
