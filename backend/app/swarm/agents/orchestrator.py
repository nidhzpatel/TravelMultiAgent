import json
from typing import Any

from app.swarm.agents.base import BaseAgent
from app.swarm.message import Message


class OrchestratorAgent(BaseAgent):
    """Team lead. Breaks down user requests and delegates to specialist agents."""

    name = "Orchestrator"
    MAX_FIX_ATTEMPTS = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fix_attempts = 0

    def run(self) -> dict[str, Any] | None:
        message = self._next_message()
        if message is None:
            return None

        task = message.task
        payload = message.payload
        user_input = payload.get("user_input", "")

        if task == "initial_plan":
            self._handle_initial_plan(user_input)
            return None

        if task == "handle_follow_up":
            self._handle_follow_up(payload)
            return None

        if task == "agent_result":
            self._handle_agent_result(payload)
            return None

        if task == "critic_result":
            self._handle_critic_result(payload)
            return None

        return None

    def _handle_initial_plan(self, user_input: str) -> None:
        # For the first version, we ask the Itinerary Architect to build a plan.
        self.send(
            "ItineraryArchitect",
            "build_initial_plan",
            {"user_input": user_input},
        )

    def _handle_follow_up(self, payload: dict[str, Any]) -> None:
        intent = payload.get("intent", "general_follow_up")
        details = payload.get("details", {})
        user_input = payload.get("user_input", "")

        # Reset fix counter for a new request.
        self._fix_attempts = 0

        # Handle both old-style (modify_itinerary + what_to_change) and
        # new-style (modify_transit / modify_stay / modify_experience) intents.
        if intent in ("modify_transit", "modify_itinerary"):
            target = details.get("what_to_change", "transit")
            if target in ("transit", "flight", "train", "bus") or intent == "modify_transit":
                self.send("TransitAgent", "modify_transit", {"user_input": user_input, "details": details})
            elif target in ("stay", "hotel", "accommodation"):
                self.send("StayAgent", "modify_stay", {"user_input": user_input, "details": details})
            elif target in ("activity", "activities", "sightseeing", "day", "experience"):
                self.send("ExperienceAgent", "modify_experience", {"user_input": user_input, "details": details})
            else:
                self.send("ItineraryArchitect", "modify_plan", {"user_input": user_input, "details": details})

        elif intent == "modify_stay":
            self.send("StayAgent", "modify_stay", {"user_input": user_input, "details": details})

        elif intent == "modify_experience":
            self.send("ExperienceAgent", "modify_experience", {"user_input": user_input, "details": details})

        elif intent == "list_alternatives":
            category = details.get("category", "hotel")
            if category in ("hotel", "stay"):
                self.send("StayAgent", "list_alternatives", {"user_input": user_input, "details": details})
            elif category in ("flight", "transit"):
                self.send("TransitAgent", "list_alternatives", {"user_input": user_input, "details": details})
            else:
                self.send("ExperienceAgent", "list_alternatives", {"user_input": user_input, "details": details})

        elif intent == "new_plan":
            self.send("ItineraryArchitect", "build_initial_plan", {"user_input": user_input})

        else:
            self.send("ResearchAgent", "answer_question", {"user_input": user_input})

    def _handle_agent_result(self, payload: dict[str, Any]) -> None:
        sender = payload.get("sender")
        result_type = payload.get("type")

        # If a specialist produced a plan change, route it to the itinerary architect.
        if result_type == "plan_change":
            self.send(
                "ItineraryArchitect",
                "apply_change",
                {
                    "change_source": sender,
                    "change": payload.get("change"),
                    "summary": payload.get("summary", ""),
                },
            )
            return

        # If a specialist produced alternatives, send them to the concierge for display.
        if result_type == "alternatives":
            self.send(
                "Concierge",
                "present_response",
                {
                    "type": "alternatives",
                    "message": payload.get("summary", "Here are some alternatives."),
                    "alternatives": payload.get("items", []),
                },
            )
            return

        # If a specialist answered a question, forward it to the concierge.
        if result_type == "answer":
            self.send(
                "Concierge",
                "present_response",
                {
                    "type": "text",
                    "message": payload.get("answer", ""),
                },
            )
            return

    def _handle_critic_result(self, payload: dict[str, Any]) -> None:
        valid = payload.get("valid", True)
        issues = payload.get("issues", [])
        updated_itinerary = payload.get("updated_itinerary")

        if not valid and self._fix_attempts < self.MAX_FIX_ATTEMPTS:
            # Send back to the architect to fix.
            self._fix_attempts += 1
            self.send(
                "ItineraryArchitect",
                "fix_issues",
                {"issues": issues, "itinerary": updated_itinerary},
            )
            return

        # Approved (or we gave up fixing). Accept the plan.
        self._fix_attempts = 0

        # Approved. Store the updated itinerary and tell the concierge to respond.
        self.blackboard.set("current_itinerary", updated_itinerary)

        self.send(
            "Concierge",
            "present_response",
            {
                "type": "itinerary_update",
                "message": payload.get("summary", "I've updated your plan."),
                "itinerary": updated_itinerary,
            },
        )
