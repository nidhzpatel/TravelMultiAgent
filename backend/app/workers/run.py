"""Standalone planning worker process entrypoint."""

import socket
import time

from app.config import get_settings
from app.observability.planning import log_planning_outcome
from app.persistence.job_repository import SqlAlchemyPlanningJobRepository
from app.workers.planning import PlanningWorker


def run_forever() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for the planning worker")
    repository = SqlAlchemyPlanningJobRepository(settings.database_url)
    worker = PlanningWorker(repository, worker_id=f"{socket.gethostname()}-{id(repository)}", lease_seconds=settings.planning_worker_lease_seconds)
    while True:
        result = worker.run_once()
        if result is None:
            time.sleep(settings.planning_worker_poll_seconds)
        else:
            log_planning_outcome(result)


if __name__ == "__main__":
    run_forever()
