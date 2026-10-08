"""Deterministic evidence expiry and fact-status normalization."""

from datetime import datetime, timezone

from app.domain.contracts import Evidence, Fact, FactStatus, Money, PriceStatus, ProviderOutcomeStatus


def evidence_is_stale(evidence: Evidence, at: datetime | None = None) -> bool:
    now = at or datetime.now(timezone.utc)
    return evidence.expires_at is not None and evidence.expires_at <= now


def normalize_fact(fact: Fact, evidence: tuple[Evidence, ...], at: datetime | None = None) -> Fact:
    """Downgrade claims when their field evidence is absent, expired, or not retainable."""
    if fact.status is not FactStatus.VERIFIED:
        return fact
    indexed = {item.id: item for item in evidence}
    supporting = [indexed[item_id] for item_id in fact.evidence_ids if item_id in indexed]
    if not supporting:
        return fact.model_copy(update={"status": FactStatus.UNVERIFIED})
    if any(evidence_is_stale(item, at) for item in supporting):
        return fact.model_copy(update={"status": FactStatus.STALE})
    if any(not item.retention_permitted or item.provider_outcome is not ProviderOutcomeStatus.SUCCESS for item in supporting):
        return fact.model_copy(update={"status": FactStatus.UNVERIFIED})
    return fact


def normalize_money(money: Money, evidence: tuple[Evidence, ...], at: datetime | None = None) -> Money:
    if money.status is not PriceStatus.VERIFIED:
        return money
    indexed = {item.id: item for item in evidence}
    supporting = [indexed[item_id] for item_id in money.evidence_ids if item_id in indexed]
    if not supporting or any(evidence_is_stale(item, at) or not item.retention_permitted or item.provider_outcome is not ProviderOutcomeStatus.SUCCESS for item in supporting):
        return money.model_copy(update={"status": PriceStatus.ESTIMATED})
    return money
