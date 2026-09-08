import json
import re
from typing import Any

from app.swarm.agents.base import BaseAgent


class ConciergeAgent(BaseAgent):
    """User-facing agent. Decides whether to answer directly or invoke the swarm."""

    name = "Concierge"

    # Keyword rules for common follow-up patterns.
    _MODIFY_TRANSIT_KEYWORDS = [
        "flight", "train", "bus", "transport", "travel", "fly", "railway", "airport",
        "station", "cab", "taxi", "instead of flight", "instead of train",
    ]
    _MODIFY_STAY_KEYWORDS = [
        "hotel", "stay", "accommodation", "room", "resort", "guest house", "hostel",
    ]
    _MODIFY_EXPERIENCE_KEYWORDS = [
        "activity", "activities", "sightseeing", "museum", "beach", "temple", "restaurant",
        "food", "shopping", "replace", "change day", "add day", "remove day",
    ]
    _ALTERNATIVES_KEYWORDS = [
        "alternative", "alternatives", "other options", "other hotels", "other flights",
        "list hotels", "list flights", "show me hotels", "show me flights", "cheaper",
    ]

    def run(self) -> dict[str, Any] | None:
        message = self._next_message()
        if message is None:
            return None

        task = message.task
        payload = message.payload

        # The orchestrator asks the concierge to present a final response to the user.
        if task == "present_response":
            return {
                "type": payload.get("type", "text"),
                "message": payload.get("message", ""),
                "itinerary": payload.get("itinerary"),
                "alternatives": payload.get("alternatives"),
                "suggested_actions": payload.get("suggested_actions", []),
            }

        user_input = payload.get("user_input", "")
        current_itinerary = self.blackboard.get("current_itinerary")

        # The API layer handles initial plan creation; the swarm only modifies existing plans.
        if current_itinerary is None:
            return {
                "type": "text",
                "message": "I don't have a trip planned yet. Let me create one for you first.",
            }

        # Use deterministic keyword classification first, LLM as fallback.
        classification = self._keyword_classify(user_input)
        if classification is None:
            classification = self._llm_classify(user_input, current_itinerary)

        if classification["type"] == "direct_answer":
            return {
                "type": "text",
                "message": classification["answer"],
            }

        # Otherwise hand off to the orchestrator swarm.
        self.send(
            "Orchestrator",
            "handle_follow_up",
            {
                "user_input": user_input,
                "intent": classification.get("intent"),
                "details": classification.get("details", {}),
            },
        )
        return None

    def _keyword_classify(self, user_input: str) -> dict[str, Any] | None:
        text_lower = user_input.lower()

        # Alternatives are usually explicit list/show requests.
        if any(kw in text_lower for kw in self._ALTERNATIVES_KEYWORDS):
            category = "hotel"
            if any(kw in text_lower for kw in ["flight", "train", "transport"]):
                category = "transit"
            elif any(kw in text_lower for kw in ["activity", "restaurant", "thing to do", "sightseeing"]):
                category = "experience"
            return {
                "type": "list_alternatives",
                "intent": "list_alternatives",
                "details": {"category": category, "criteria": user_input},
            }

        # Modification requests.
        if any(kw in text_lower for kw in self._MODIFY_TRANSIT_KEYWORDS):
            return {
                "type": "modify_itinerary",
                "intent": "modify_transit",
                "details": {"what_to_change": "transit", "criteria": user_input},
            }

        if any(kw in text_lower for kw in self._MODIFY_STAY_KEYWORDS):
            return {
                "type": "modify_itinerary",
                "intent": "modify_stay",
                "details": {"what_to_change": "stay", "criteria": user_input},
            }

        if any(kw in text_lower for kw in self._MODIFY_EXPERIENCE_KEYWORDS):
            return {
                "type": "modify_itinerary",
                "intent": "modify_experience",
                "details": {"what_to_change": "experience", "criteria": user_input},
            }

        return None

    def _llm_classify(self, user_input: str, current_itinerary: dict[str, Any] | None) -> dict[str, Any]:
        prompt = self._build_classification_prompt(user_input, current_itinerary)
        raw = self._llm_invoke(prompt)

        parsed = self._extract_json(raw)
        if parsed is not None:
            return parsed

        # Fallback: treat as a general question.
        return {
            "type": "direct_answer",
            "answer": raw or "I'm not sure how to help with that. Could you rephrase?",
        }

    def _extract_json(self, raw: str) -> dict[str, Any] | None:
        """Best-effort JSON extraction from LLM output."""
        if not raw:
            return None

        # Try direct parsing first.
        try:
            return json.loads(raw.strip())
        except Exception:
            pass

        # Look for a JSON object.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

        return None

    def _build_classification_prompt(self, user_input: str, current_itinerary: dict[str, Any] | None) -> str:
        destination = current_itinerary.get("destination", "the destination") if current_itinerary else "the destination"
        return (
            "You are a travel concierge classifier. Respond ONLY with a JSON object. No prose.\n\n"
            f"Destination: {destination}\n"
            f"User message: {user_input}\n\n"
            "Choose exactly one of these types:\n"
            "- direct_answer: general travel question that does NOT require changing the itinerary.\n"
            "- modify_itinerary: user wants to change transport, stay, days, or activities.\n"
            "- list_alternatives: user wants to see other hotels, flights, or activities.\n"
            "- new_plan: user wants to plan a completely new trip.\n\n"
            "Output ONLY this JSON shape (no markdown, no comments):\n"
            '{\n'
            '  "type": "modify_itinerary",\n'
            '  "intent": "modify_transit",\n'
            '  "details": {"what_to_change": "transit", "criteria": "..."}\n'
            '}\n'
        )
