from __future__ import annotations

from app.domain.contracts import Trip
from app.operations.contracts import OperationKind, ProposalRequest
from app.persistence.repositories import VersionConflictError


class OperationValidationError(ValueError):
    pass


def apply_operations(trip: Trip, proposal: ProposalRequest) -> Trip:
    """Deterministic v2 operation application; LLM output never calls this directly."""
    result = trip
    for operation in proposal.operations:
        if operation.kind is OperationKind.READ:
            continue
        if operation.kind is OperationKind.REPLACE and operation.path == "title" and operation.value:
            result = result.model_copy(update={"title": operation.value})
            continue
        raise OperationValidationError(f"Unsupported operation: {operation.kind}")
    return result


def commit_replace(repository, trip: Trip, proposal: ProposalRequest):
    if proposal.expected_version < 1:
        raise VersionConflictError("Expected version is invalid")
    return repository.append_version(apply_operations(trip, proposal), proposal.expected_version)
