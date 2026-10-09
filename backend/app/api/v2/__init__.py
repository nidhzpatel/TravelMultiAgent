from fastapi import APIRouter

from app.api.v2.providers import router as providers_router
from app.api.v2.trips import router as trips_router

router = APIRouter()
router.include_router(trips_router)
router.include_router(providers_router)

__all__ = ["router"]
