from pathlib import Path
import unittest


ROOT = Path(__file__).parents[2]


class V7FrontendContractTests(unittest.TestCase):
    def test_workspace_exposes_bounded_job_progress_and_terminal_states(self) -> None:
        component = (ROOT / "frontend" / "src" / "components" / "PlanningProgress.tsx").read_text(encoding="utf-8")
        workspace = (ROOT / "frontend" / "src" / "components" / "V2ProposalWorkspace.tsx").read_text(encoding="utf-8")
        for status in ("NEEDS_INPUT", "SUCCEEDED", "FAILED", "CANCELLED", "EXPIRED"):
            self.assertIn(status, component)
        self.assertIn("TERMINAL.has(job.status)", component)
        self.assertIn("<progress", component)
        self.assertIn("cancelPlanningJob", component)
        self.assertIn("onAccepted", component)
        self.assertIn("<PlanningProgress", workspace)

    def test_api_supports_nonblocking_job_lifecycle(self) -> None:
        api = (ROOT / "frontend" / "src" / "api.ts").read_text(encoding="utf-8")
        for function_name in (
            "createPlanningJob",
            "listPlanningJobs",
            "getPlanningJob",
            "getPlanningJobEvents",
            "cancelPlanningJob",
        ):
            self.assertIn(f"function {function_name}", api)


if __name__ == "__main__":
    unittest.main()
