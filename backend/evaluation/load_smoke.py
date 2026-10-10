"""Bounded authenticated HTTP load smoke for a deployed staging environment."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import statistics
import time

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--p95-budget-ms", type=float, default=1500)
    args = parser.parse_args()
    if not 1 <= args.requests <= 10000 or not 1 <= args.concurrency <= 100:
        raise SystemExit("Load bounds are invalid")

    def request() -> tuple[int, float]:
        started = time.perf_counter()
        response = httpx.get(f"{args.base_url.rstrip('/')}/v2/trips", headers={"Authorization": f"Bearer {args.token}"}, timeout=10)
        return response.status_code, (time.perf_counter() - started) * 1000

    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda _: request(), range(args.requests)))
    latencies = sorted(item[1] for item in results)
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)]
    errors = sum(1 for status, _ in results if status >= 500)
    payload = {"requests": args.requests, "concurrency": args.concurrency, "p50_ms": statistics.median(latencies), "p95_ms": p95, "server_errors": errors, "passed": p95 <= args.p95_budget_ms and errors == 0}
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
