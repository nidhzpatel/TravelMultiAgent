"""Fail closed unless every dated production release gate has evidence."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


def evaluate(gates: dict, evidence: dict) -> list[str]:
    failures: list[str] = []
    if not evidence.get("release_candidate"):
        failures.append("release_candidate is required")
    if not evidence.get("performed_at"):
        failures.append("performed_at is required")
    else:
        try:
            performed = datetime.fromisoformat(evidence["performed_at"])
            if performed.tzinfo is None or performed > datetime.now(timezone.utc):
                failures.append("performed_at must be a valid past timezone-aware timestamp")
        except (TypeError, ValueError):
            failures.append("performed_at is invalid")
    for name in gates["required"]:
        item = evidence.get(name)
        if not isinstance(item, dict) or item.get("passed") is not True:
            failures.append(f"{name} has not passed")
        elif name != "operational_owner" and not item.get("artifact"):
            failures.append(f"{name} needs an evidence artifact")
    restore = evidence.get("restore_drill", {})
    if restore.get("passed"):
        if restore.get("rpo_seconds", gates["rpo_max_seconds"] + 1) > gates["rpo_max_seconds"]:
            failures.append("restore_drill exceeds RPO")
        if restore.get("rto_seconds", gates["rto_max_seconds"] + 1) > gates["rto_max_seconds"]:
            failures.append("restore_drill exceeds RTO")
    security = evidence.get("security_scan", {})
    if security.get("passed") and security.get("critical_findings") != 0:
        failures.append("security_scan has unresolved critical findings")
    provider = evidence.get("provider_coverage", {})
    if provider.get("passed") and (not provider.get("market") or not provider.get("artifact")):
        failures.append("provider_coverage needs a market and artifact")
    owner = evidence.get("operational_owner", {})
    if owner.get("passed") and (not owner.get("team") or not owner.get("on_call")):
        failures.append("operational_owner needs team and on_call")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--gates", type=Path, default=Path(__file__).parents[1] / "qualification/release-gates.json")
    args = parser.parse_args()
    failures = evaluate(json.loads(args.gates.read_text()), json.loads(args.evidence.read_text()))
    print(json.dumps({"qualified": not failures, "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
