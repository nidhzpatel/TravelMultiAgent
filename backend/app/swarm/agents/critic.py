import json
from typing import Any

from app.swarm.agents.base import BaseAgent


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

        prompt = (
            "You are a critical itinerary reviewer. Check the updated itinerary for issues.\n\n"
            f"Change source: {change_source}\n"
            f"Summary: {summary}\n\n"
            f"Itinerary: {json.dumps(updated)}\n\n"
            "Check:\n"
            "1. Total cost does not exceed total_budget by a large margin.\n"
            "2. Every day has a stay and at least one activity.\n"
            "3. Transit legs are realistic and match the destinations.\n"
            "4. No duplicate or contradictory entries.\n\n"
            "Respond ONLY with JSON:\n"
            '{"valid": true|false, "issues": ["issue 1", "issue 2"], "summary": "..."}'
        )
        raw = self._llm_invoke(prompt)

        try:
            result = json.loads(raw)
        except Exception:
            result = {"valid": True, "issues": [], "summary": summary}

        valid = result.get("valid", True)
        issues = result.get("issues", [])

        if not valid and issues:
            self.send(
                "Orchestrator",
                "critic_result",
                {
                    "valid": False,
                    "issues": issues,
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
