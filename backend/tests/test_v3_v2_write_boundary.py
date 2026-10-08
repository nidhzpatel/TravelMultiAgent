from pathlib import Path
import unittest


class V2WriteBoundaryTests(unittest.TestCase):
    def test_v2_trip_api_does_not_import_legacy_swarm_or_chat_mutators(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "app/api/v2/trips.py").read_text()
        self.assertNotIn("SwarmRunner", source)
        self.assertNotIn("chat_store", source)
        self.assertNotIn("_persist_stores", source)
        self.assertIn("commit_replace", source)


if __name__ == "__main__":
    unittest.main()
