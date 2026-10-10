"""Run a one-step Alembic rollback and recovery against a disposable database."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm-disposable-target", action="store_true")
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if not args.confirm_disposable_target:
        raise SystemExit("Refusing migration rollback without --confirm-disposable-target")
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is required")
    commands = (["alembic", "upgrade", "head"], ["alembic", "downgrade", "-1"], ["alembic", "upgrade", "head"], ["alembic", "current", "--check-heads"])
    for command in commands:
        subprocess.run(command, cwd="backend", check=True)
    args.evidence.write_text(json.dumps({"passed": True, "performed_at": datetime.now(timezone.utc).isoformat(), "steps": ["upgrade", "downgrade-one", "upgrade", "check-heads"]}, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
