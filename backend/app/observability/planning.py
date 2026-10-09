"""PII-safe planning-job outcome logging."""

import logging

from app.planning.jobs import PlanningJob

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
