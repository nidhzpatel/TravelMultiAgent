from pathlib import Path
from tempfile import TemporaryDirectory
import os
import subprocess
import unittest


class V2MigrationTests(unittest.TestCase):
    def test_upgrade_and_downgrade_render_sql(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            target = Path(directory) / "upgrade.sql"
            command = [str(backend / ".venv/bin/alembic"), "-c", str(backend / "alembic.ini"), "upgrade", "head", "--sql"]
            environment = {**os.environ, "PYTHONPATH": str(backend)}
            completed = subprocess.run(command, cwd=backend, env=environment, capture_output=True, text=True, check=True)
            target.write_text(completed.stdout)
            self.assertIn("CREATE TABLE trips", target.read_text())
            down = subprocess.run(
                [str(backend / ".venv/bin/alembic"), "-c", str(backend / "alembic.ini"), "downgrade", "head:base", "--sql"],
                cwd=backend, env=environment, capture_output=True, text=True, check=True,
            )
            self.assertIn("DROP TABLE", down.stdout)
