"""Provider boundary shared by production adapters."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

from app.domain.contracts import Evidence, ProviderOutcomeStatus

T = TypeVar("T")


class ProviderResult(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: ProviderOutcomeStatus
    value: T | None = None
    evidence: tuple[Evidence, ...] = ()
    error_code: str | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> "ProviderResult[T]":
        if self.status in {ProviderOutcomeStatus.SUCCESS, ProviderOutcomeStatus.MOCK} and self.value is None:
            raise ValueError("Successful provider outcomes require a value")
        if self.status in {ProviderOutcomeStatus.NO_RESULTS, ProviderOutcomeStatus.UNAVAILABLE, ProviderOutcomeStatus.ERROR} and self.value is not None:
            raise ValueError("Unsuccessful provider outcomes cannot carry a value")
        if self.status is ProviderOutcomeStatus.ERROR and not self.error_code:
            raise ValueError("Provider errors require an error code")
        return self
