import json
import re
from typing import Any

from app.swarm.agents.base import BaseAgent


class StayAgent(BaseAgent):
    """Handles hotel and accommodation changes."""

    name = "StayAgent"

    # Ordered most-specific-first so "non-veg" wins over "veg".
    _FOOD_PATTERNS = [
        "non-vegetarian", "non veg", "nonveg",
        "gluten-free", "gluten free",
        "vegetarian", "jain", "vegan", "halal", "kosher", "veg",
    ]

    def _extract_food_preference(self, user_input: str) -> str | None:
        text = (user_input or "").lower()
        for preference in self._FOOD_PATTERNS:
            if preference in text:
                return preference
        return None

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
            # Persist a stated food preference deterministically. The LLM may echo
            # the CURRENT preference from the itinerary context, so an explicit
            # preference in the user's words always wins; otherwise keep the LLM's
            # value (it may be null).
            extracted = self._extract_food_preference(user_input)
            if extracted:
                change["food_preference"] = extracted
            elif not change.get("food_preference"):
                change["food_preference"] = None
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
            "You are an accommodation expert. The user wants to change hotels in their existing itinerary.\n"
            "Hard requirements for every stay you propose: it must serve the traveler's food preference, "
            "breakfast and dinner must be included in the rate (lunch is always on the traveler), it must "
            "fit the trip's travel style and budget, and why_this_choice must state the food match and "
            "meal inclusion.\n\n"
            f"User request: {user_input}\n\n"
            f"Current itinerary context: {self._itinerary_context(current)}\n\n"
            "Respond ONLY with a raw JSON object in this exact shape (no markdown, no comments):\n"
            '{\n'
            '  "section": "stay",\n'
            '  "summary": "Short description of the change",\n'
            '  "food_preference": "the food preference this change applies to, if the user stated one; otherwise null",\n'
            '  "stays": [\n'
            '    {\n'
            '      "night_number": 1,\n'
            '      "hotel_name": "Hotel Name",\n'
            '      "location": "Area / City",\n'
            '      "room_type": "budget | balanced | luxury room",\n'
            '      "estimated_cost_usd": 0,\n'
            '      "why_this_choice": "Reason, including food match and breakfast + dinner included",\n'
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
            "food_preference": None,
            "stays": [],
        }

    def _find_hotel_alternatives(self, user_input: str, current: dict[str, Any] | None) -> list[dict[str, Any]]:
        prompt = (
            "You are an accommodation expert. List alternative hotels for this trip. Every option must "
            "serve the traveler's food preference and include breakfast and dinner in the rate; say so "
            "in the why field.\n\n"
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
