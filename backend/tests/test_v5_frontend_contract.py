from pathlib import Path
import unittest


class P5FrontendContractTests(unittest.TestCase):
    def test_map_and_timeline_share_keyboard_accessible_selection(self) -> None:
        root = Path(__file__).resolve().parents[2] / "frontend/src/components"
        map_source = (root / "MapPanel.tsx").read_text()
        timeline_source = (root / "ScheduledTimeline.tsx").read_text()
        workspace = (root / "V2ProposalWorkspace.tsx").read_text()
        self.assertIn('type="button"', map_source)
        self.assertIn("aria-pressed", map_source)
        self.assertIn('type="button"', timeline_source)
        self.assertIn("aria-pressed", timeline_source)
        self.assertGreaterEqual(workspace.count("selectedDestinationId"), 4)
        self.assertIn("No verified coordinates", map_source)

    def test_v2_feasibility_code_has_no_llm_route_source(self) -> None:
        backend = Path(__file__).resolve().parents[1] / "app"
        source = "\n".join((backend / relative).read_text() for relative in (
            "providers/routes.py", "planning/scheduler.py", "validation/timeline.py", "validation/snapshot.py"
        ))
        self.assertNotIn("get_chat_llm", source)
        self.assertNotIn("crew.tools", source)


if __name__ == "__main__":
    unittest.main()
