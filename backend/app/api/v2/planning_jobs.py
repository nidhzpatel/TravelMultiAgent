"""Non-blocking durable planning-job API."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v2.trips import get_repository
from app.persistence.job_repository import SqlAlchemyPlanningJobRepository
from app.persistence.repositories import SqlAlchemyTripRepository
from app.planning.jobs import PlanningJob, PlanningJobEvent, PlanningJobRequest
from app.security.identity import Principal, current_principal, enforce_rate_limit

router = APIRouter(prefix="/v2/trips", tags=["v2 planning jobs"], dependencies=[Depends(enforce_rate_limit)])


def get_job_repository(repository: SqlAlchemyTripRepository = Depends(get_repository)) -> SqlAlchemyPlanningJobRepository:
    return SqlAlchemyPlanningJobRepository("", engine=repository.engine)


def _trip_and_role(trip_id: str, principal: Principal, repository: SqlAlchemyTripRepository):
    trip = repository.get(trip_id)
    role = repository.member_role(trip_id, principal.subject)
    if trip is None or role not in {"OWNER", "EDITOR", "VIEWER"}:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip, role


def _job_for_trip(job_id: str, trip_id: str, jobs: SqlAlchemyPlanningJobRepository) -> PlanningJob:
    job = jobs.get(job_id)
    if job is None or job.trip_id != trip_id:
        raise HTTPException(status_code=404, detail="Planning job not found")
    return job


@router.post("/{trip_id}/planning-jobs", response_model=PlanningJob, status_code=status.HTTP_202_ACCEPTED)
def create_planning_job(
    trip_id: str,
    request: PlanningJobRequest,
    principal: Principal = Depends(current_principal),
    repository: SqlAlchemyTripRepository = Depends(get_repository),
    jobs: SqlAlchemyPlanningJobRepository = Depends(get_job_repository),
) -> PlanningJob:
    trip, role = _trip_and_role(trip_id, principal, repository)
    if role not in {"OWNER", "EDITOR"}:
        raise HTTPException(status_code=403, detail="Trip edit access required")
    try:
        return jobs.create(trip_id, principal.subject, trip.version, request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{trip_id}/planning-jobs", response_model=tuple[PlanningJob, ...])
def list_planning_jobs(
    trip_id: str,
    principal: Principal = Depends(current_principal),
    repository: SqlAlchemyTripRepository = Depends(get_repository),
    jobs: SqlAlchemyPlanningJobRepository = Depends(get_job_repository),
) -> tuple[PlanningJob, ...]:
    _trip_and_role(trip_id, principal, repository)
    return jobs.list_for_trip(trip_id)


@router.get("/{trip_id}/planning-jobs/{job_id}", response_model=PlanningJob)
def get_planning_job(
    trip_id: str,
    job_id: str,
    principal: Principal = Depends(current_principal),
    repository: SqlAlchemyTripRepository = Depends(get_repository),
    jobs: SqlAlchemyPlanningJobRepository = Depends(get_job_repository),
) -> PlanningJob:
    _trip_and_role(trip_id, principal, repository)
    return _job_for_trip(job_id, trip_id, jobs)


@router.get("/{trip_id}/planning-jobs/{job_id}/events", response_model=tuple[PlanningJobEvent, ...])
def get_planning_job_events(
    trip_id: str,
    job_id: str,
    after: int = Query(default=0, ge=0),
    principal: Principal = Depends(current_principal),
    repository: SqlAlchemyTripRepository = Depends(get_repository),
    jobs: SqlAlchemyPlanningJobRepository = Depends(get_job_repository),
) -> tuple[PlanningJobEvent, ...]:
    _trip_and_role(trip_id, principal, repository)
    _job_for_trip(job_id, trip_id, jobs)
    return jobs.events(job_id, after)


@router.post("/{trip_id}/planning-jobs/{job_id}/cancel", response_model=PlanningJob)
def cancel_planning_job(
    trip_id: str,
    job_id: str,
    principal: Principal = Depends(current_principal),
    repository: SqlAlchemyTripRepository = Depends(get_repository),
    jobs: SqlAlchemyPlanningJobRepository = Depends(get_job_repository),
) -> PlanningJob:
    _, role = _trip_and_role(trip_id, principal, repository)
    if role not in {"OWNER", "EDITOR"}:
        raise HTTPException(status_code=403, detail="Trip edit access required")
    _job_for_trip(job_id, trip_id, jobs)
    return jobs.request_cancel(job_id)
