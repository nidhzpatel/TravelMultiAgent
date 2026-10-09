from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from urllib.parse import urlparse


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VoyageMind AI"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # LLM configuration (Ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"

    # Gemini is the primary LLM; Ollama is the fallback when Gemini hits rate limits.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

    # External API keys (only Serper is required for search tools)
    serper_api_key: str = ""
    flight_provider_url: str = ""
    flight_provider_token: str = ""
    hotel_provider_url: str = ""
    hotel_provider_token: str = ""
    planning_worker_lease_seconds: int = 30
    planning_worker_poll_seconds: float = 1.0

    # Required by the v2 persistence/API path. Production validation is added in P2.
    database_url: str = ""
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    rate_limit_per_minute: int = 60
    rate_limit_window_seconds: int = 60
    session_secret: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def require_postgres_database_url(database_url: str | None = None) -> str:
    """Validate the production v2 storage target without opening a connection."""
    value = database_url or get_settings().database_url
    scheme = urlparse(value).scheme
    if scheme not in {"postgresql", "postgresql+psycopg"}:
        raise RuntimeError("DATABASE_URL must use postgresql+psycopg in production")
    return value


def validate_production_settings(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if settings.environment.lower() != "production":
        return
    require_postgres_database_url(settings.database_url)
    if not (settings.oidc_issuer and settings.oidc_audience and settings.oidc_jwks_url):
        raise RuntimeError("OIDC issuer, audience, and JWKS URL are required in production")
    if len(settings.session_secret) < 32:
        raise RuntimeError("SESSION_SECRET must contain at least 32 characters in production")
    if any(origin == "*" for origin in settings.cors_origins):
        raise RuntimeError("Wildcard CORS origins are forbidden in production")
