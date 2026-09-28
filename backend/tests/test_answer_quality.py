"""Offline regressions: real routing, patching and acceptance; scripted model outputs."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.swarm.blackboard import Blackboard
from app.swarm.message import Message
from app.swarm.agents.concierge import ConciergeAgent
from app.swarm.agents.critic import CriticAgent
from app.swarm.agents.orchestrator import OrchestratorAgent
from app.swarm.agents.itinerary_architect import ItineraryArchitectAgent
from app.swarm.agents.research import ResearchAgent
from app.swarm.runner import SwarmRunner


def fixture():
    return {"destination": "Goa", "origin": "Ahmedabad", "currency": "INR",
            "exchange_rate": 80, "total_budget_usd": 1000, "total_budget": 80000,
            "actual_calculated_cost_usd": 300, "actual_calculated_cost": 24000,
            "travelers": 2, "notes": [], "inclusions": [], "exclusions": [],
            "transit_summary": "Train", "stay_summary": "Two nights",
            "sightseeing_summary": "Beaches", "days": [
                {"day_number": i, "date": f"2026-10-0{i}", "theme": "Beaches",
                 "activities": [{"activity_name": "Lunch", "time_slot": "12:00 - 13:00",
                                 "location": "Goa", "category": "food", "notes": "Estimate",
                                 "estimated_cost_usd": 10, "estimated_cost": 800}],
                 "transit_legs": [{"day_number": i, "from_location": "A", "to_location": "B",
                                   "mode": "train", "provider": "Estimate", "duration_minutes": 60,
                                   "notes": "Estimate", "estimated_cost_usd": 20, "estimated_cost": 1600}],
                 "stay": None, "daily_transit_cost": 1600, "daily_transit_cost_usd": 20,
                 "daily_activity_cost": 800, "daily_activity_cost_usd": 10,
                 "daily_stay_cost": 0, "daily_stay_cost_usd": 0,
                 "total_daily_cost": 2400, "total_daily_cost_usd": 30} for i in (1, 2)]}


class FakeLLM:
    def __init__(self, output):
        self.output = output
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content=self.output)


class QualityTests(unittest.TestCase):
    def test_flight_question_is_read_only(self):
        agent = ConciergeAgent(Blackboard())
        result = agent._keyword_classify("When is my flight?")
        self.assertFalse(result and result.get("intent", "").startswith("modify"))

    def test_hotel_question_is_read_only(self):
        result = ConciergeAgent(Blackboard())._keyword_classify("Does my hotel include dinner?")
        self.assertFalse(result and result.get("intent", "").startswith("modify"))

    def test_explicit_edit_still_routes(self):
        result = ConciergeAgent(Blackboard())._keyword_classify("Change my flight to a train")
        self.assertEqual(result["intent"], "modify_transit")

    def test_alternatives_still_route(self):
        result = ConciergeAgent(Blackboard())._keyword_classify("List other flights")
        self.assertEqual(result["intent"], "list_alternatives")

    def test_transit_edit_preserves_other_days(self):
        data = fixture()
        original = copy.deepcopy(data["days"][1])
        ItineraryArchitectAgent(Blackboard())._replace_transit_leg(data, {
            "day_number": 1, "from_location": "A", "to_location": "B",
            "mode": "bus", "estimated_cost_usd": 12})
        self.assertEqual(data["days"][1], original)
        self.assertEqual(data["days"][0]["transit_legs"][0]["mode"], "bus")

    def test_transit_currency(self):
        data = fixture()
        ItineraryArchitectAgent(Blackboard())._replace_transit_leg(data, {
            "day_number": 1, "from_location": "A", "to_location": "B", "estimated_cost_usd": 12})
        self.assertEqual(data["days"][0]["transit_legs"][0]["estimated_cost"], 960)

    def test_critic_rejects_malformed_output(self):
        agent = CriticAgent(Blackboard(), FakeLLM("not JSON"))
        agent._validate({"updated_itinerary": fixture()})
        self.assertIs(agent.outbox[0].payload["valid"], False)

    def test_critic_rejects_false_without_issues(self):
        agent = CriticAgent(Blackboard(), FakeLLM('{"valid": false, "issues": []}'))
        agent._validate({"updated_itinerary": fixture()})
        self.assertIs(agent.outbox[0].payload["valid"], False)

    def test_critic_rejects_string_boolean(self):
        agent = CriticAgent(Blackboard(), FakeLLM('{"valid": "false", "issues": []}'))
        agent._validate({"updated_itinerary": fixture()})
        self.assertIs(agent.outbox[0].payload["valid"], False)

    def test_failed_repairs_preserve_original(self):
        original = fixture()
        board = Blackboard({"current_itinerary": original})
        agent = OrchestratorAgent(board)
        agent._fix_attempts = agent.MAX_FIX_ATTEMPTS
        candidate = fixture()
        candidate["destination"] = "Wrong destination"
        agent._handle_critic_result({"valid": False, "issues": ["wrong destination"],
                                    "updated_itinerary": candidate})
        self.assertEqual(board.get("current_itinerary"), original)
        self.assertEqual(agent.outbox[-1].payload["type"], "text")

    def test_research_receives_itinerary(self):
        llm = FakeLLM("The itinerary lists a train.")
        ResearchAgent(Blackboard({"current_itinerary": fixture()}), llm)._answer("What transport is planned?")
        self.assertIn("Ahmedabad", str(llm.prompts[0]))
        self.assertIn("transit_legs", str(llm.prompts[0]))

    def test_invalid_classifier_shape_does_not_crash(self):
        agent = ConciergeAgent(Blackboard({"current_itinerary": fixture()}), FakeLLM("[]"))
        agent.receive(Message("User", "Concierge", "user_message", {"user_input": "Explain that"}))
        agent.run()

    def test_unsupported_radius_reports_failure(self):
        with patch("app.swarm.runner.get_chat_llm", return_value=FakeLLM("{}")):
            result = SwarmRunner(Blackboard({"current_itinerary": fixture()})).run("Only within 100 km")
        self.assertNotIn("I've processed your request", result["message"])
        self.assertEqual(result["type"], "text")

    def test_display_retains_internal_activity_cost(self):
        from app.main import _apply_display_pricing
        data = _apply_display_pricing(fixture(), "balanced")
        self.assertEqual(data["days"][0]["activities"][0]["estimated_cost_usd"], 10)
        self.assertEqual(data["days"][0]["daily_activity_cost_usd"], 10)

    def test_budget_does_not_discount_prices(self):
        from app.main import _scale_itinerary_to_budget
        data = fixture()
        original = copy.deepcopy(data["days"])
        _scale_itinerary_to_budget(data, 10, 80)
        self.assertEqual(data["days"], original)
        self.assertTrue(any("budget" in n.lower() for n in data["notes"]))


if __name__ == "__main__":
    unittest.main()
