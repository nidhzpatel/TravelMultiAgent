import json
import re
from typing import Any

from app.swarm.agents.base import BaseAgent


class ExperienceAgent(BaseAgent):
    """Handles activities, sightseeing, restaurants, and day-level changes."""

    name = "ExperienceAgent"

    def run(self) -> dict[str, Any] | None:
        message = self._next_message()
        if message is None:
            return None

        task = message.task
        payload = message.payload
        user_input = payload.get("user_input", "")
        current = self.blackboard.get("current_itinerary")

        if task == "modify_experience":
            change = self._plan_experience_change(user_input, current)
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
            alternatives = self._find_experience_alternatives(user_input, current)
            self.send(
                "Orchestrator",
                "agent_result",
                {
                    "sender": self.name,
                    "type": "alternatives",
                    "items": alternatives,
                    "summary": "Here are some alternative activities.",
                },
            )
            return None

        return None

    def _plan_experience_change(self, user_input: str, current: dict[str, Any] | None) -> dict[str, Any]:
        prompt = (
            "You are a local experiences expert. The user wants to change activities in their existing itinerary.\n"
            "Rules: keep the trip's famous/iconic places and top-rated places in the plan unless the user "
            "explicitly asks to drop one; every activity must stay within the day's region and the travel "
            "radius; food activities are lunch only (breakfast and dinner are included at the hotel) and "
            "must match the traveler's food preference; activity costs cover lunch or local cabs only, "
            "never entrance fees.\n\n"
            f"User request: {user_input}\n\n"
            f"Current itinerary context: {self._itinerary_context(current)}\n\n"
            "Respond ONLY with a raw JSON object in this exact shape (no markdown, no comments):\n"
            '{\n'
            '  "section": "experience",\n'
            '  "summary": "Short description of the change",\n'
            '  "days": [\n'
            '    {\n'
            '      "day_number": 1,\n'
            '      "theme": "Theme for the day",\n'
            '      "activities": [\n'
            '        {"time_slot": "09:00 AM - 11:00 AM", "activity_name": "...", "location": "...", "category": "sightseeing|food|transit", "estimated_cost_usd": 0, "notes": "..."}\n'
            '      ]\n'
            '    }\n'
            '  ]\n'
            '}\n'
        )
        raw = self._llm_invoke(prompt)
        parsed = self._extract_json(raw)
        if isinstance(parsed, dict):
            return parsed
        return {
            "section": "experience",
            "summary": "Updated activities based on your request.",
            "days": [],
        }

    def _find_experience_alternatives(self, user_input: str, current: dict[str, Any] | None) -> list[dict[str, Any]]:
        prompt = (
            "You are a local experiences expert. List alternative activities or restaurants for this trip. "
            "Restaurants must match the traveler's food preference; everything must lie within the day's "
            "region and the travel radius.\n\n"
            f"User request: {user_input}\n\n"
            f"Current itinerary context: {self._itinerary_context(current)}\n\n"
            "Respond ONLY with a raw JSON array like (no markdown, no comments):\n"
            '[\n'
            '  {"name": "Activity Name", "location": "Area", "category": "sightseeing|food|shopping", "estimated_cost_usd": 30, "notes": "..."}\n'
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
