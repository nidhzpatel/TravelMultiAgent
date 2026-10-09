from pathlib import Path
import unittest


class ProviderFrontendContractTests(unittest.TestCase):
    def test_provider_ui_discloses_mock_stale_unknown_and_evidence_states(self) -> None:
        root = Path(__file__).resolve().parents[2] / "frontend/src/components"
        flight = (root / "FlightCard.tsx").read_text()
        hotel = (root / "HotelCard.tsx").read_text()
        weather = (root / "WeatherPanel.tsx").read_text()
        status = (root / "ProviderStatus.tsx").read_text()
        drawer = (root / "AlternativeDrawer.tsx").read_text()
        self.assertIn("Development fixture", flight)
        self.assertIn("Offer stale", flight)
        self.assertIn("Price unknown", flight)
        self.assertIn("Development fixture", hotel)
        self.assertIn("Rate stale", hotel)
        self.assertIn("No supported forecast", weather)
        self.assertIn("Provider data has not been requested", status)
        self.assertIn("EvidenceBadge", drawer)

    def test_handoff_requires_live_nonstale_evidence(self) -> None:
        root = Path(__file__).resolve().parents[2] / "frontend/src/components"
        for name in ("FlightCard.tsx", "HotelCard.tsx"):
            source = (root / name).read_text()
            self.assertIn("item.handoff_url && !stale && !mock", source)
            self.assertIn('type="button"', source)

    def test_v2_provider_specialists_do_not_use_llm_or_legacy_tools(self) -> None:
        planning = Path(__file__).resolve().parents[1] / "app/planning"
        source = "\n".join((planning / name).read_text() for name in (
            "flight_specialist.py", "stay_specialist.py", "places_specialist.py", "weather_specialist.py", "provider_service.py"
        ))
        self.assertNotIn("get_chat_llm", source)
        self.assertNotIn("crew.tools", source)


if __name__ == "__main__":
    unittest.main()
