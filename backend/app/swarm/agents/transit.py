import json
import re
from typing import Any

from app.swarm.agents.base import BaseAgent


class TransitAgent(BaseAgent):
    """Handles flight, train, bus, and local transport changes."""

    name = "TransitAgent"

    def run(self) -> dict[str, Any] | None:
        message = self._next_message()
        if message is None:
            return None

        task = message.task
        payload = message.payload
        user_input = payload.get("user_input", "")
        current = self.blackboard.get("current_itinerary")

        if task == "modify_transit":
            change = self._plan_transit_change(user_input, current)
            self.send(
                "Orchestrator",
                "agent_result",
                {
                    "sender": self.name,
                    "type": "plan_change",
                    "change": change,
                    "summary": change.get("summary", ""),
                },
            )
            return None

        if task == "list_alternatives":
            alternatives = self._find_transit_alternatives(user_input, current)
            self.send(
                "Orchestrator",
                "agent_result",
                {
                    "sender": self.name,
                    "type": "alternatives",
                    "items": alternatives,
                    "summary": "Here are some alternative transport options.",
                },
            )
            return None

        return None

    def _plan_transit_change(self, user_input: str, current: dict[str, Any] | None) -> dict[str, Any]:
        prompt = (
            "You are a transit expert. The user wants to change transport in their existing itinerary.\n"
            "Choose each leg's mode by distance: walk under 2 km; auto/rickshaw/cab for 2–15 km; "
            "bus/metro/train for 15–300 km; flight only beyond ~300 km or when the user explicitly "
            "wants one. If a leg runs around mealtime, note a food stop that matches the traveler's "
            "food preference.\n\n"
            f"User request: {user_input}\n\n"
            f"Current itinerary context: {self._itinerary_context(current)}\n\n"
            "Respond ONLY with a raw JSON object in this exact shape (no markdown, no comments):\n"
            '{\n'
            '  "section": "transit",\n'
            '  "summary": "Short description of the change",\n'
            '  "transit_legs": [\n'
            '    {\n'
            '      "day_number": 1,\n'
            '      "from_location": "Origin city",\n'
            '      "to_location": "Destination city",\n'
            '      "mode": "train|flight|bus|cab",\n'
            '      "provider": "Operator name",\n'
            '      "estimated_cost_usd": 0,\n'
            '      "duration_minutes": 0,\n'
            '      "notes": "distance and why this mode"\n'
            '    }\n'
            '  ]\n'
            '}\n'
        )
        raw = self._llm_invoke(prompt)
        parsed = self._extract_json(raw)
        if isinstance(parsed, dict):
            return parsed
        return {
            "section": "transit",
            "summary": "Changed transport based on your request.",
            "transit_legs": [],
        }

    def _find_transit_alternatives(self, user_input: str, current: dict[str, Any] | None) -> list[dict[str, Any]]:
        prompt = (
            "You are a transit expert. List alternative transport options for this trip. "
            "Choose modes by distance: walk under 2 km; auto/rickshaw/cab 2–15 km; bus/metro/train "
            "15–300 km; flight beyond ~300 km. Keep the traveler's food preference in mind for "
            "longer legs with meal service.\n\n"
            f"User request: {user_input}\n\n"
            f"Current itinerary context: {self._itinerary_context(current)}\n\n"
            "Respond ONLY with a raw JSON array like (no markdown, no comments):\n"
            '[\n'
            '  {"name": "Option name", "mode": "train|flight|bus", "estimated_cost_usd": 120, "duration_minutes": 480, "notes": "..."}\n'
            ']\n'
        )
        raw = self._llm_invoke(prompt)
        parsed = self._extract_json(raw)
        if isinstance(parsed, list):
            return parsed
        return []

    def _itinerary_context(self, current: dict[str, Any] | None) -> str:
        return self._context(current)

    def _extract_json(self, raw: str) -> Any | None:
        if not raw:
            return None
        try:
            return json.loads(raw.strip())
        except Exception:
            pass
        match = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return None
