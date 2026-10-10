"""Create an encrypted-storage-ready PostgreSQL custom-format backup and manifest."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    output_dir = Path(os.environ.get("BACKUP_DIR", "/backups"))
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = output_dir / f"voyagemind-{stamp}.dump"
    with tempfile.NamedTemporaryFile(dir=output_dir, prefix=".backup-", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    environment = {**os.environ, "PGDATABASE": database_url}
    try:
        subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--file", str(temporary_path)], env=environment, check=True)
        digest = hashlib.sha256(temporary_path.read_bytes()).hexdigest()
        temporary_path.replace(destination)
        manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "filename": destination.name, "sha256": digest, "size_bytes": destination.stat().st_size}
        destination.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    finally:
        temporary_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
