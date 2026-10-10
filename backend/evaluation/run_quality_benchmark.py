"""Run the versioned deterministic release benchmark."""

from collections import defaultdict
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT))


def main() -> int:
    definition = json.loads((Path(__file__).with_name("quality_benchmark_v1.json")).read_text(encoding="utf-8"))
    results = []
    categories: dict[str, list[bool]] = defaultdict(list)
    for case in definition["cases"]:
        suite = unittest.defaultTestLoader.loadTestsFromName(case["test"])
        stream = io.StringIO()
        with redirect_stdout(stream), redirect_stderr(stream):
            result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
        passed = result.wasSuccessful()
        categories[case["category"]].append(passed)
        results.append({**case, "passed": passed})
    total = len(results)
    passed_count = sum(1 for item in results if item["passed"])
    payload = {"version": definition["version"], "mode": "deterministic_fixture", "passed": passed_count, "total": total, "pass_rate": passed_count / total if total else 0, "category_pass_rate": {name: sum(values) / len(values) for name, values in categories.items()}, "cases": results}
    print(json.dumps(payload, indent=2))
    return 0 if payload["pass_rate"] >= definition["minimum_pass_rate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
