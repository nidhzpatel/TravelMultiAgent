"""API integration checks with scripted LLM and isolated persistence; no network."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from app import main
from app.accounting import recompute_costs
from app.schemas import ChatSession, MasterTravelItinerary, TravelPlanResponse
from test_answer_quality import fixture, FakeLLM


class ApiQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.stack = []
        for target, value in (("STORE_FILE", Path(self.temp.name) / "store.json"),
                              ("chat_store", {}), ("itinerary_store", {})):
            patcher = patch.object(main, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        data = fixture()
        recompute_costs(data)
        self.itinerary = MasterTravelItinerary.model_validate(data)
        main.chat_store["test"] = ChatSession(id="test", title="Fixture", created_at="", updated_at="",
                                             messages=[], current_itinerary=self.itinerary)
        main.itinerary_store["test"] = self.itinerary
        self.client = TestClient(main.app)

    def test_question_round_trip_preserves_plan(self):
        with patch("app.swarm.runner.get_chat_llm", return_value=FakeLLM("Your plan lists a train.")):
            response = self.client.post("/chat/test/message", json={"message": "What transport is planned?"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"]["type"], "text")
        self.assertEqual(main.chat_store["test"].current_itinerary, self.itinerary)

    def test_weather_abstains_without_model_claim(self):
        llm = FakeLLM("Guaranteed sunshine")
        with patch("app.swarm.runner.get_chat_llm", return_value=llm):
            response = self.client.post("/chat/test/message", json={"message": "What is the weather tomorrow?"})
        self.assertIn("don't have live sources", response.json()["message"]["content"])
        self.assertEqual(len(llm.prompts), 0)

    def test_rejected_update_does_not_claim_success(self):
        with patch.object(main.SwarmRunner, "run", return_value={
            "type": "itinerary_update", "message": "Done!", "itinerary": {"days": "invalid"}}):
            response = self.client.post("/chat/test/message", json={"message": "Change day 2"})
        self.assertEqual(response.json()["message"]["type"], "text")
        self.assertIn("unchanged", response.json()["message"]["content"])
        self.assertEqual(main.chat_store["test"].current_itinerary, self.itinerary)

    def test_persistence_and_pdf_do_not_reprice(self):
        main._persist_stores()
        original = self.itinerary.model_dump()
        main.chat_store.clear()
        main.itinerary_store.clear()
        main._load_stores()
        self.assertEqual(main.itinerary_store["test"].model_dump(), original)
        self.assertEqual(main.chat_store["test"].current_itinerary.model_dump(), original)
        response = self.client.get("/plan/test/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_clarifying_flow_preserves_combined_request(self):
        with patch.object(main, "_create_plan_from_prompt", new=AsyncMock(return_value=TravelPlanResponse(
            status="clarifying", error="Missing required fields: start_date"))):
            response = self.client.post("/chat", json={"message": "Plan a Goa trip"})
        sid = response.json()["session_id"]
        with patch.object(main, "_create_plan_from_prompt", new=AsyncMock(return_value=TravelPlanResponse(
            status="completed", itinerary=self.itinerary))) as planner:
            response = self.client.post(f"/chat/{sid}/message", json={"message": "October 1"})
        self.assertEqual(planner.call_args.args[0], "Plan a Goa trip\nOctober 1")
        self.assertEqual(response.json()["message"]["type"], "itinerary_update")

    def test_cost_aggregation_is_idempotent_and_retains_prices(self):
        data = fixture()
        recompute_costs(data)
        self.assertEqual(data["actual_calculated_cost_usd"], 66)
        self.assertEqual(data["actual_calculated_cost"], 5280)
        previous = copy.deepcopy(data)
        recompute_costs(data)
        self.assertEqual(data, previous)

    def test_unknown_costs_disclosed(self):
        data = fixture()
        data["days"][0]["activities"][0]["estimated_cost_usd"] = None
        recompute_costs(data)
        self.assertTrue(any("unknown" in n for n in data["notes"]))

    def test_explicit_edit_round_trip(self):
        class SequenceLLM:
            def __init__(self):
                self.responses = iter([
                    json.dumps({"section": "transit", "summary": "Changed day 1 to bus",
                                "transit_legs": [{"day_number": 1, "from_location": "A",
                                                  "to_location": "B", "mode": "bus", "estimated_cost_usd": 12}]}),
                    '{"valid": true, "issues": []}',
                ])

            def invoke(self, prompt):
                from types import SimpleNamespace
                return SimpleNamespace(content=next(self.responses))

        old_day_two = self.itinerary.days[1].model_dump()
        with patch("app.swarm.runner.get_chat_llm", return_value=SequenceLLM()):
            response = self.client.post("/chat/test/message", json={"message": "Change day 1 train to bus"})
        body = response.json()
        self.assertEqual(body["message"]["type"], "itinerary_update")
        updated = body["session"]["current_itinerary"]
        self.assertEqual(updated["days"][1], old_day_two)
        self.assertEqual(updated["days"][0]["transit_legs"][0]["estimated_cost"], 960)
        self.assertEqual(updated["actual_calculated_cost_usd"], 57.2)

    def test_nonfinite_cost_rejected(self):
        data = fixture()
        data["days"][0]["transit_legs"][0]["estimated_cost_usd"] = float("nan")
        with self.assertRaises(ValueError):
            recompute_costs(data)


if __name__ == "__main__":
    unittest.main()
