from __future__ import annotations

from dataclasses import dataclass

from app.operations.contracts import Operation, OperationKind, ProposalRequest


@dataclass(frozen=True)
class IntentResolution:
    proposal: ProposalRequest | None = None
    question: str | None = None
    answer: str | None = None


def resolve_message(message: str, expected_version: int, idempotency_key: str) -> IntentResolution:
    """Small deterministic resolver; unknown or ambiguous text never mutates a trip."""
    text = message.strip().lower()
    if "flight" in text and any(token in text for token in ("when", "what", "show", "read")):
        return IntentResolution(answer="No flight is stored in this trip version yet.")
    if text.startswith("rename trip to "):
        title = message.strip()[len("rename trip to "):].strip()
        if title:
            return IntentResolution(proposal=ProposalRequest(expected_version=expected_version, idempotency_key=idempotency_key, operations=[Operation(kind=OperationKind.REPLACE, path="title", value=title)]))
    if text.startswith("add interest "):
        interest = message.strip()[len("add interest "):].strip()
        if interest:
            return IntentResolution(proposal=ProposalRequest(expected_version=expected_version, idempotency_key=idempotency_key, operations=[Operation(kind=OperationKind.ADD, path="preferences.interests", value=interest)]))
    if text.startswith("remove interest "):
        interest = message.strip()[len("remove interest "):].strip()
        if interest:
            return IntentResolution(proposal=ProposalRequest(expected_version=expected_version, idempotency_key=idempotency_key, operations=[Operation(kind=OperationKind.REMOVE, path="preferences.interests", value=interest)]))
    if text.startswith("set pace to "):
        pace = text[len("set pace to "):].strip()
        if pace in {"slow", "balanced", "fast"}:
            return IntentResolution(proposal=ProposalRequest(expected_version=expected_version, idempotency_key=idempotency_key, operations=[Operation(kind=OperationKind.REPLAN, path="preferences.pace", value=pace)]))
    if "hotel" in text and ("second" in text or "another" in text):
        return IntentResolution(question="Which stored hotel alternative should replace the current stay?")
    return IntentResolution(question="I need a specific change, such as ‘rename trip to …’ or ‘add interest …’.")
