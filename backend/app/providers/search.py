from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.providers.base import ProviderCapabilities, ProviderResult


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    query: str = Field(min_length=1, max_length=500)
    market: str = Field(min_length=2, max_length=10)
    language: str = Field(default="en", min_length=2, max_length=10)
    limit: int = Field(default=10, ge=1, le=20)


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    title: str
    snippet: str
    reference_url: str
    evidence_ids: tuple[str, ...]


class SearchProvider(Protocol):
    name: str
    capabilities: ProviderCapabilities
    def search(self, request: SearchRequest) -> ProviderResult[tuple[SearchHit, ...]]: ...
