from fastapi import APIRouter

from app.api.v2.providers import router as providers_router
from app.api.v2.planning_jobs import router as planning_jobs_router
from app.api.v2.trips import router as trips_router
from app.api.v2.collaboration import router as collaboration_router

router = APIRouter()
router.include_router(trips_router)
router.include_router(providers_router)
router.include_router(planning_jobs_router)
router.include_router(collaboration_router)

__all__ = ["router"]
