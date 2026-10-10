"""Minimal production ASGI application for the authenticated v2 product."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v2 import router as v2_router
from app.config import get_settings, validate_production_settings
from app.observability.middleware import ObservabilityMiddleware
from app.security.middleware import CsrfMiddleware, SecurityHeadersMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_production_settings(settings)
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan, docs_url=None, redoc_url=None)
app.include_router(v2_router)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CsrfMiddleware)
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"])


@app.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "voyagemind-v2"}
