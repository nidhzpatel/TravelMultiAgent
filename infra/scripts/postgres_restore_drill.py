"""Restore a verified backup into a disposable empty database and record RPO/RTO."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path)
    parser.add_argument("--confirm-empty-target", action="store_true")
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if not args.confirm_empty_target:
        raise SystemExit("Refusing restore without --confirm-empty-target")
    target = os.environ.get("RESTORE_DATABASE_URL")
    if not target:
        raise SystemExit("RESTORE_DATABASE_URL is required")
    manifest = json.loads(args.backup.with_suffix(".json").read_text(encoding="utf-8"))
    if hashlib.sha256(args.backup.read_bytes()).hexdigest() != manifest["sha256"]:
        raise SystemExit("Backup checksum mismatch")
    started = time.monotonic()
    subprocess.run(["pg_restore", "--exit-on-error", "--no-owner", "--no-acl", "--dbname", target, str(args.backup)], check=True)
    subprocess.run(["psql", target, "--tuples-only", "--command", "SELECT count(*) FROM alembic_version"], check=True, capture_output=True, text=True)
    finished_at = datetime.now(timezone.utc)
    created_at = datetime.fromisoformat(manifest["created_at"])
    evidence = {"performed_at": finished_at.isoformat(), "backup_created_at": created_at.isoformat(), "rpo_seconds": max(0, int((finished_at - created_at).total_seconds())), "rto_seconds": round(time.monotonic() - started, 3), "checksum_verified": True, "schema_verified": True}
    args.evidence.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
