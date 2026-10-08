from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OperationKind(StrEnum):
    READ = "READ"
    ADD = "ADD"
    REMOVE = "REMOVE"
    REPLACE = "REPLACE"
    MOVE = "MOVE"
    REORDER = "REORDER"
    REPLAN = "REPLAN"


class Operation(BaseModel):
    """A narrow mutation request; arbitrary dictionaries are rejected."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: OperationKind
    target_id: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9]*_[0-9a-f]{32}$")
    path: Literal["title", "preferences.interests", "preferences.pace"] | None = None
    value: str | None = Field(default=None, max_length=200)
    values: tuple[str, ...] | None = Field(default=None, max_length=100)
    index: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_shape(self) -> "Operation":
        if self.kind is OperationKind.READ:
            if self.value is not None or self.values is not None or self.index is not None:
                raise ValueError("READ cannot include mutation values")
            return self
        if self.kind is OperationKind.REPLACE and self.path == "title" and self.value:
            return self
        if self.kind in {OperationKind.ADD, OperationKind.REMOVE} and self.path == "preferences.interests" and self.value:
            return self
        if self.kind is OperationKind.MOVE and self.path == "preferences.interests" and self.value and self.index is not None:
            return self
        if self.kind is OperationKind.REORDER and self.path == "preferences.interests" and self.values:
            return self
        if self.kind is OperationKind.REPLAN and self.path == "preferences.pace" and self.value in {"slow", "balanced", "fast"}:
            return self
        raise ValueError(f"Invalid fields for {self.kind} operation")


class ProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=16, max_length=255)
    operations: tuple[Operation, ...] = Field(min_length=1, max_length=20)
