"""Bounded, request-local planning orchestration with typed specialist output."""

from __future__ import annotations

from decimal import Decimal
from typing import Callable, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.domain.contracts import Trip, TripReadiness
from app.planning.jobs import PlanningCandidate


class SpecialistResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    specialist: str = Field(min_length=1, max_length=80)
    candidate_facts: dict[str, object] = Field(default_factory=dict)
    candidate_trip: Trip | None = None
    tokens_used: int = Field(default=0, ge=0)
    cost_usd: Decimal = Field(default=Decimal("0"), ge=0)


class PlanningSpecialist(Protocol):
    def run(self, trip: Trip) -> SpecialistResult: ...


class DeterministicDraftSpecialist:
    """Build the minimum typed draft after validating required brief fields."""

    def run(self, trip: Trip) -> SpecialistResult:
        return SpecialistResult(
            specialist="deterministic-draft",
            candidate_facts={
                "destination": trip.brief.destination_text,
                "travelers": trip.brief.travelers,
                "date_range": [trip.brief.start_date.isoformat(), trip.brief.end_date.isoformat()],
            },
            candidate_trip=trip.model_copy(update={"readiness": TripReadiness.ACTION_REQUIRED}),
        )


class PlanningNeedsInput(Exception):
    def __init__(self, missing_fields: tuple[str, ...]) -> None:
        super().__init__(", ".join(missing_fields))
        self.missing_fields = missing_fields


class BoundedPlanningOrchestrator:
    def __init__(
        self,
        specialists: tuple[PlanningSpecialist, ...] | None = None,
        critic: Callable[[Trip, tuple[SpecialistResult, ...]], tuple[str, ...]] | None = None,
        max_specialists: int = 8,
    ) -> None:
        self.specialists = specialists or (DeterministicDraftSpecialist(),)
        self.critic = critic or (lambda _trip, _results: ())
        self.max_specialists = max_specialists

    def plan(
        self,
        trip: Trip,
        on_specialist: Callable[[str, int, int], None] | None = None,
    ) -> tuple[PlanningCandidate, int, Decimal]:
        missing = tuple(
            field
            for field, value in (
                ("origin", trip.brief.origin),
                ("start_date", trip.brief.start_date),
                ("end_date", trip.brief.end_date),
            )
            if value is None
        )
        if missing:
            raise PlanningNeedsInput(missing)
        if len(self.specialists) > self.max_specialists:
            raise ValueError("Planning specialist bound exceeded")
        results: list[SpecialistResult] = []
        total = len(self.specialists)
        for index, specialist in enumerate(self.specialists, start=1):
            if on_specialist:
                on_specialist(type(specialist).__name__, index, total)
            results.append(SpecialistResult.model_validate(specialist.run(trip)))
        typed_results = tuple(results)
        # The Critic contributes advisory notes once. Pydantic and deterministic
        # domain validation remain the only commit authority.
        notes = tuple(str(note)[:500] for note in self.critic(trip, typed_results))
        candidate_trip = trip.model_copy(update={"readiness": TripReadiness.ACTION_REQUIRED})
        for result in typed_results:
            if result.candidate_trip is None:
                continue
            proposed = Trip.model_validate(result.candidate_trip)
            if proposed.id != trip.id or proposed.owner_id != trip.owner_id:
                raise ValueError("Planning specialist changed immutable trip identity")
            candidate_trip = proposed.model_copy(update={"readiness": TripReadiness.ACTION_REQUIRED})
        candidate_trip = Trip.model_validate(candidate_trip)
        candidate = PlanningCandidate(trip=candidate_trip, advisory_notes=notes)
        return candidate, sum(item.tokens_used for item in typed_results), sum((item.cost_usd for item in typed_results), Decimal("0"))
