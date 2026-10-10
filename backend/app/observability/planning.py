"""PII-safe planning-job outcome logging."""

import logging

from app.planning.jobs import PlanningJob
from app.observability.metrics import emit_metrics

logger = logging.getLogger("voyagemind.planning")


def log_planning_outcome(job: PlanningJob) -> None:
    logger.info(
        "planning_job status=%s attempts=%d tokens=%d cost_usd=%s error=%s",
        job.status.value,
        job.attempt_count,
        job.tokens_used,
        job.cost_used_usd,
        job.error_code or "none",
    )
    emit_metrics(
        "planning_job_terminal",
        {"PlanningJobCount": 1, "PlanningAttemptCount": job.attempt_count, "PlanningTokensUsed": job.tokens_used, "PlanningCostUsd": float(job.cost_used_usd)},
        {"status": job.status.value, "error_code": job.error_code or "none"},
    )
