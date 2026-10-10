"""Exercise the authenticated, version-pinned staging product surface."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path
import secrets
import urllib.error
import urllib.request


def request(base_url: str, token: str, method: str, path: str, payload: dict | None = None) -> tuple[int, bytes, dict[str, str]]:
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    call = urllib.request.Request(f"{base_url.rstrip('/')}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(call, timeout=30) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {path} returned {exc.code}: {exc.read().decode(errors='replace')}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("STAGING_BASE_URL"))
    parser.add_argument("--token", default=os.environ.get("STAGING_OIDC_TOKEN"))
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    if not args.base_url or not args.token:
        raise SystemExit("STAGING_BASE_URL and STAGING_OIDC_TOKEN are required")

    start = date.today() + timedelta(days=30)
    payload = {
        "title": "Release qualification trip",
        "brief": {"origin": "Ahmedabad", "destination_text": "Goa", "start_date": start.isoformat(), "end_date": (start + timedelta(days=2)).isoformat()},
        "budget": {"target": {"amount": "1000", "currency": "USD", "status": "USER_PROVIDED", "provenance": "USER"}},
        "idempotency_key": f"staging-e2e-{secrets.token_hex(12)}",
    }
    status, body, _ = request(args.base_url, args.token, "POST", "/v2/trips", payload)
    trip = json.loads(body)
    trip_id, version = trip["trip_id"], trip["version"]
    checks = {"create": status == 201}
    checks["trip"] = request(args.base_url, args.token, "GET", f"/v2/trips/{trip_id}/versions/{version}")[0] == 200
    checks["budget"] = request(args.base_url, args.token, "GET", f"/v2/trips/{trip_id}/budget?version={version}")[0] == 200
    pdf_status, pdf, headers = request(args.base_url, args.token, "GET", f"/v2/trips/{trip_id}/export.pdf?version={version}")
    checks["versioned_pdf"] = pdf_status == 200 and pdf.startswith(b"%PDF") and "application/pdf" in headers.get("Content-Type", "")
    evidence = {"passed": all(checks.values()), "trip_id": trip_id, "version": version, "checks": checks}
    args.evidence.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
