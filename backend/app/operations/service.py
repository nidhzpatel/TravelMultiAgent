from __future__ import annotations

from app.domain.contracts import Trip
from app.operations.contracts import OperationKind, ProposalRequest
from app.persistence.repositories import VersionConflictError


class OperationValidationError(ValueError):
    pass


def changed_fields(before: Trip, after: Trip) -> tuple[str, ...]:
    """Return the exact canonical fields changed by a deterministic proposal."""
    fields: list[str] = []
    if before.title != after.title:
        fields.append("title")
    if before.preferences.interests != after.preferences.interests:
        fields.append("preferences.interests")
    if before.preferences.pace != after.preferences.pace:
        fields.append("preferences.pace")
    return tuple(fields)


def apply_operations(trip: Trip, proposal: ProposalRequest) -> Trip:
    """Deterministic v2 operation application; LLM output never calls this directly."""
    result = trip
    for operation in proposal.operations:
        if operation.kind is OperationKind.READ:
            continue
        if operation.target_id is not None and operation.target_id != result.id:
            raise OperationValidationError("Operation target does not match the trip")
        if operation.kind is OperationKind.REPLACE and operation.path == "title" and operation.value:
            result = result.model_copy(update={"title": operation.value})
            continue
        if operation.path == "preferences.interests":
            interests = list(result.preferences.interests)
            if operation.kind is OperationKind.ADD and operation.value and operation.value not in interests:
                interests.append(operation.value)
            elif operation.kind is OperationKind.REMOVE and operation.value in interests:
                interests.remove(operation.value)
            elif operation.kind is OperationKind.MOVE and operation.value in interests and operation.index is not None:
                interests.remove(operation.value)
                interests.insert(min(operation.index, len(interests)), operation.value)
            elif operation.kind is OperationKind.REORDER and operation.values is not None and sorted(operation.values) == sorted(interests):
                interests = list(operation.values)
            else:
                raise OperationValidationError(f"Invalid interest operation: {operation.kind}")
            result = result.model_copy(update={"preferences": result.preferences.model_copy(update={"interests": tuple(interests)})})
            continue
        if operation.kind is OperationKind.REPLAN and operation.path == "preferences.pace" and operation.value in {"slow", "balanced", "fast"}:
            result = result.model_copy(update={"preferences": result.preferences.model_copy(update={"pace": operation.value})})
            continue
        raise OperationValidationError(f"Unsupported operation: {operation.kind}")
    return result


def commit_replace(repository, trip: Trip, proposal: ProposalRequest):
    if proposal.expected_version < 1:
        raise VersionConflictError("Expected version is invalid")
    current = repository.get(trip.id)
    if current is None or current.version != proposal.expected_version:
        raise VersionConflictError("Trip changed; fetch the latest version before retrying")
    updated = apply_operations(trip, proposal)
    if updated == trip:
        return current
    return repository.append_version(updated, proposal.expected_version)
