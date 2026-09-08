import json
import re
from typing import Any

from app.swarm.agents.base import BaseAgent


class StayAgent(BaseAgent):
    """Handles hotel and accommodation changes."""

    name = "StayAgent"

    def run(self) -> dict[str, Any] | None:
        message = self._next_message()
        if message is None:
            return None

        task = message.task
        payload = message.payload
        user_input = payload.get("user_input", "")
        current = self.blackboard.get("current_itinerary")

        if task == "modify_stay":
            change = self._plan_stay_change(user_input, current)
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
            alternatives = self._find_hotel_alternatives(user_input, current)
            self.send(
                "Orchestrator",
                "agent_result",
                {
                    "sender": self.name,
                    "type": "alternatives",
                    "items": alternatives,
                    "summary": "Here are some alternative hotels.",
                },
            )
            return None

        return None

    def _plan_stay_change(self, user_input: str, current: dict[str, Any] | None) -> dict[str, Any]:
        prompt = (
            "You are an accommodation expert. The user wants to change hotels in their existing itinerary.\n\n"
            f"User request: {user_input}\n\n"
            f"Current itinerary context: {self._itinerary_context(current)}\n\n"
            "Respond ONLY with a raw JSON object in this exact shape (no markdown, no comments):\n"
            '{\n'
            '  "section": "stay",\n'
            '  "summary": "Short description of the change",\n'
            '  "stays": [\n'
            '    {\n'
            '      "night_number": 1,\n'
            '      "hotel_name": "Hotel Name",\n'
            '      "location": "Area / City",\n'
            '      "room_type": "budget | balanced | luxury room",\n'
            '      "estimated_cost_usd": 0,\n'
            '      "why_this_choice": "Reason for picking this hotel",\n'
            '      "booking_notes": "Notes for booking"\n'
            '    }\n'
            '  ]\n'
            '}\n'
        )
        raw = self._llm_invoke(prompt)
        parsed = self._extract_json(raw)
        if isinstance(parsed, dict):
            return parsed
        return {
            "section": "stay",
            "summary": "Updated accommodation based on your request.",
            "stays": [],
        }

    def _find_hotel_alternatives(self, user_input: str, current: dict[str, Any] | None) -> list[dict[str, Any]]:
        prompt = (
            "You are an accommodation expert. List alternative hotels for this trip.\n\n"
            f"User request: {user_input}\n\n"
            f"Current itinerary context: {self._itinerary_context(current)}\n\n"
            "Respond ONLY with a raw JSON array like (no markdown, no comments):\n"
            '[\n'
            '  {"name": "Hotel Name", "location": "Area", "estimated_cost_usd": 120, "why": "..."}\n'
            ']\n'
        )
        raw = self._llm_invoke(prompt)
        parsed = self._extract_json(raw)
        if isinstance(parsed, list):
            return parsed
        return []

    def _itinerary_context(self, current: dict[str, Any] | None) -> str:
        if not current:
            return "No existing itinerary."
        first_stay = None
        if current.get("days"):
            first_stay = current["days"][0].get("stay")
        return json.dumps({
            "destination": current.get("destination"),
            "origin": current.get("origin"),
            "currency": current.get("currency"),
            "stay_summary": current.get("stay_summary"),
            "current_first_stay": first_stay,
            "travelers": current.get("travelers"),
        })

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
