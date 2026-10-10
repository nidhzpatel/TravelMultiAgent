from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys
import unittest

from infra.scripts.qualify_release import evaluate


ROOT = Path(__file__).parents[2]


class ReleaseQualificationTests(unittest.TestCase):
    def test_release_gate_fails_closed_and_accepts_complete_dated_evidence(self) -> None:
        gates = json.loads((ROOT / "infra/qualification/release-gates.json").read_text())
        incomplete = json.loads((ROOT / "infra/qualification/evidence.example.json").read_text())
        self.assertIn("provider_coverage has not passed", evaluate(gates, incomplete))
        evidence = {name: {"passed": True, "artifact": f"artifact://{name}"} for name in gates["required"]}
        evidence["release_candidate"] = "sha256:test"
        evidence.update({
            "performed_at": datetime.now(timezone.utc).isoformat(),
            "restore_drill": {"passed": True, "rpo_seconds": 300, "rto_seconds": 600, "artifact": "artifact://restore"},
            "security_scan": {"passed": True, "critical_findings": 0, "artifact": "artifact://security"},
            "provider_coverage": {"passed": True, "market": "test-market", "coverage_percent": 95, "artifact": "artifact://coverage"},
            "operational_owner": {"passed": True, "team": "platform", "on_call": "schedule://primary"},
        })
        self.assertEqual(evaluate(gates, evidence), [])

    def test_versioned_quality_benchmark_passes(self) -> None:
        completed = subprocess.run(
            [sys.executable, "backend/evaluation/run_quality_benchmark.py"],
            cwd=ROOT,
            env={**__import__("os").environ, "PYTHONPATH": "backend"},
            capture_output=True,
            text=True,
            check=True,
        )
        result = json.loads(completed.stdout)
        self.assertEqual((result["version"], result["passed"], result["total"]), ("1.0.0", 6, 6))

    def test_delivery_files_enforce_nonroot_encryption_and_fail_closed_scans(self) -> None:
        backend = (ROOT / "backend/Dockerfile").read_text()
        frontend = (ROOT / "frontend/Dockerfile").read_text()
        terraform = (ROOT / "infra/terraform/main.tf").read_text()
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("USER voyagemind", backend)
        self.assertIn("requirements-production.txt", backend)
        self.assertIn("app.production:app", backend)
        production = (ROOT / "backend/app/production.py").read_text()
        self.assertNotIn("app.crew", production)
        self.assertNotIn("app.swarm", production)
        self.assertNotIn("app.main", production)
        self.assertIn("nginx-unprivileged", frontend)
        for contract in (r"storage_encrypted\s*=\s*true", r"backup_retention_period", r"deletion_protection", r"assign_public_ip\s*=\s*false", r"deployment_circuit_breaker"):
            self.assertRegex(terraform, contract)
        for contract in ("pip-audit", "npm audit", "trivy-action", "sbom-action", "exit-code: '1'"):
            self.assertIn(contract, workflow)

    def test_restore_drill_requires_explicit_empty_target_confirmation(self) -> None:
        with TemporaryDirectory() as directory:
            backup = Path(directory) / "backup.dump"
            backup.write_bytes(b"fixture")
            result = subprocess.run([sys.executable, "infra/scripts/postgres_restore_drill.py", str(backup), "--evidence", str(Path(directory) / "evidence.json")], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing restore", result.stderr)

    def test_migration_rollback_drill_requires_disposable_target_confirmation(self) -> None:
        with TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "infra/scripts/migration_rollback_drill.py", "--evidence", str(Path(directory) / "evidence.json")], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing migration rollback", result.stderr)


if __name__ == "__main__":
    unittest.main()
