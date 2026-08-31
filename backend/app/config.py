from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VoyageMind AI"
    app_version: str = "0.1.0"
    debug: bool = False

    # LLM configuration (Ollama)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:latest"

    # External API keys (only Serper is required for search tools)
    serper_api_key: str = ""

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
