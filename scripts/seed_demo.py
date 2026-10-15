"""Prepare a running NEXUS for the demo walkthrough (talks to the API only).

    make demo      # backend must be running (make dev)
"""

from __future__ import annotations

import json
import sys
import urllib.request

API = "http://127.0.0.1:8000/api/v1"


def call(path: str, method: str = "GET", body: dict | None = None) -> object:
    req = urllib.request.Request(
        f"{API}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def main() -> int:
    try:
        ready = call("/health/ready")
    except OSError:
        print("Backend not reachable on :8000 — run `make dev` first.")
        return 1
    print("readiness:", ready["status"])  # type: ignore[index]
    call("/chaos/reset", "POST", {})
    print("demo-service restored to baseline")
    call("/chaos/auto-heal", "PUT", {"enabled": True})
    print("auto-heal on")
    tickets = call("/tickets")
    print(f"{len(tickets)} tickets in the local tracker")  # type: ignore[arg-type]
    print("\nOpen http://localhost:3000 and follow docs/DEMO_SCRIPT.md (or press ▶ Present).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
