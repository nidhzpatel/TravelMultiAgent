import json
from typing import Any

from app.swarm.agents.base import BaseAgent
from app.swarm.message import Message


class ItineraryArchitectAgent(BaseAgent):
    """Owns the master itinerary. Applies changes requested by specialist agents."""

    name = "ItineraryArchitect"

    def run(self) -> dict[str, Any] | None:
        message = self._next_message()
        if message is None:
            return None

        task = message.task
        payload = message.payload

        if task == "apply_change":
            return self._apply_change(payload)

        if task == "fix_issues":
            return self._fix_issues(payload)

        return None

    def _apply_change(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        current = self.blackboard.get("current_itinerary")
        if current is None:
            self.send(
                "Orchestrator",
                "agent_result",
                {
                    "sender": self.name,
                    "type": "answer",
                    "answer": "I don't have an existing plan to modify. Would you like to create one first?",
                },
            )
            return None

        change = payload.get("change", {})
        change_source = payload.get("change_source", "unknown")
        summary = payload.get("summary", "")

        # Apply the change by making a deep copy and patching the relevant section.
        updated = json.loads(json.dumps(current))

        if change.get("section") == "transit":
            updated["transit_summary"] = change.get("transit_summary", updated.get("transit_summary"))
            # Replace matching transit legs if day_number provided.
            for leg in change.get("transit_legs", []):
                self._replace_transit_leg(updated, leg)

        elif change.get("section") == "stay":
            updated["stay_summary"] = change.get("stay_summary", updated.get("stay_summary"))
            for stay in change.get("stays", []):
                self._replace_stay(updated, stay)

        elif change.get("section") == "experience":
            for day_update in change.get("days", []):
                self._update_day_activities(updated, day_update)

        # Forward the updated itinerary to the critic for validation.
        self.send(
            "Critic",
            "validate",
            {
                "updated_itinerary": updated,
                "change_source": change_source,
                "summary": summary,
            },
        )
        return None

    def _fix_issues(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        itinerary = payload.get("itinerary")
        issues = payload.get("issues", [])

        # For the MVP, we do a simple LLM-based fix attempt.
        prompt = (
            "You are an itinerary validator. Fix the issues below in the itinerary and return ONLY the corrected itinerary as JSON.\n\n"
            f"Issues: {json.dumps(issues)}\n\n"
            f"Itinerary: {json.dumps(itinerary)}\n\n"
            "Return only valid JSON matching the original shape."
        )
        raw = self._llm_invoke(prompt)

        try:
            fixed = json.loads(raw)
        except Exception:
            fixed = itinerary

        self.send(
            "Critic",
            "validate",
            {"updated_itinerary": fixed, "change_source": self.name, "summary": "Fixed validation issues."},
        )
        return None

    def _replace_transit_leg(self, itinerary: dict[str, Any], leg: dict[str, Any]) -> None:
        day_number = leg.get("day_number")
        for day in itinerary.get("days", []):
            day["transit_legs"] = [
                l for l in day.get("transit_legs", []) if l.get("day_number") != day_number
            ]
            day["transit_legs"].append(leg)

    def _replace_stay(self, itinerary: dict[str, Any], stay: dict[str, Any]) -> None:
        night_number = stay.get("night_number")
        for day in itinerary.get("days", []):
            if day.get("stay", {}).get("night_number") == night_number:
                day["stay"] = stay

    def _update_day_activities(self, itinerary: dict[str, Any], day_update: dict[str, Any]) -> None:
        day_number = day_update.get("day_number")
        for day in itinerary.get("days", []):
            if day.get("day_number") == day_number:
                if "activities" in day_update:
                    day["activities"] = day_update["activities"]
                if "theme" in day_update:
                    day["theme"] = day_update["theme"]
                if "region" in day_update:
                    day["region"] = day_update["region"]
