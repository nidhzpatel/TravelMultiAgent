import json
from typing import Any

from app.swarm.agents.base import BaseAgent
from app.accounting import recompute_costs
from app.schemas import MasterTravelItinerary


class CriticAgent(BaseAgent):
    """Validates itinerary changes for budget, feasibility, and consistency."""

    name = "Critic"

    def run(self) -> dict[str, Any] | None:
        message = self._next_message()
        if message is None:
            return None

        task = message.task
        payload = message.payload

        if task == "validate":
            return self._validate(payload)

        return None

    def _validate(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        updated = payload.get("updated_itinerary")
        summary = payload.get("summary", "")
        change_source = payload.get("change_source", "unknown")

        try:
            updated = MasterTravelItinerary.model_validate(updated).model_dump()
            recompute_costs(updated)
        except (ValueError, TypeError, AttributeError):
            self.send("Orchestrator", "critic_result", {
                "valid": False, "issues": ["Candidate has invalid structure or costs."],
                "updated_itinerary": updated,
            })
            return None

        prompt = (
            "You are a critical itinerary reviewer. Check the updated itinerary for issues.\n\n"
            f"Change source: {change_source}\n"
            f"Summary: {summary}\n\n"
            f"Itinerary: {json.dumps(updated)}\n\n"
            "Check:\n"
            "1. Total cost does not exceed total_budget by a large margin.\n"
            "2. Every day has a stay and at least one activity.\n"
            "3. Transit legs are realistic and match the destinations; leg modes fit the distances.\n"
            "4. No duplicate or contradictory entries.\n"
            "5. Every stay matches the trip's food_preference and includes breakfast and dinner "
            "(lunch stays self-paid).\n"
            "6. Food activities are lunch only and match the food_preference; no breakfast or "
            "dinner appears as a paid activity.\n"
            "7. Nothing is scheduled outside the trip's radius_km from the destination, and "
            "famous/top-rated places were not dropped by the change.\n\n"
            "Respond ONLY with JSON:\n"
            '{"valid": true|false, "issues": ["issue 1", "issue 2"], "summary": "..."}'
        )
        raw = self._llm_invoke(prompt)

        try:
            result = json.loads(raw)
        except Exception:
            result = None

        well_formed = (
            isinstance(result, dict)
            and type(result.get("valid")) is bool
            and isinstance(result.get("issues"), list)
            and all(isinstance(issue, str) for issue in result["issues"])
        )
        valid = well_formed and result["valid"] is True and not result["issues"]
        issues = result["issues"] if well_formed else ["Review did not return a valid verdict."]

        if not valid:
            self.send(
                "Orchestrator",
                "critic_result",
                {
                    "valid": False,
                    "issues": issues or ["Reviewer rejected this change."],
                    "updated_itinerary": updated,
                },
            )
            return None

        self.send(
            "Orchestrator",
            "critic_result",
            {
                "valid": True,
                "issues": [],
                "updated_itinerary": updated,
                "summary": summary,
            },
        )
        return None
