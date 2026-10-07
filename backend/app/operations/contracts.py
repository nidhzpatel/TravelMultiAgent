from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    path: Literal["title"] | None = None
    value: str | None = Field(default=None, max_length=200)


class ProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=16, max_length=255)
    operations: tuple[Operation, ...] = Field(min_length=1, max_length=20)
