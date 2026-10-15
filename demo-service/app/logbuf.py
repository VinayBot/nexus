"""In-memory structured log ring buffer and counters, exposed over HTTP."""

import time
import traceback
from collections import deque

LOGS: deque = deque(maxlen=500)
METRICS = {"orders_processed": 0, "errors": 0, "batches": 0, "started_at": time.time()}
RECENT: deque = deque(maxlen=40)  # (ts, ok, latency_ms) per processed order


def log(level: str, event: str, message: str = "", exc: BaseException | None = None, **fields) -> None:
    entry = {"ts": round(time.time(), 3), "level": level, "event": event, "message": message, **fields}
    if exc is not None:
        entry["traceback"] = "".join(traceback.format_exception(exc))
    LOGS.append(entry)
    if level == "ERROR":
        METRICS["errors"] += 1


def record(ok: bool, latency_ms: float) -> None:
    RECENT.append((time.time(), ok, latency_ms))
    if ok:
        METRICS["orders_processed"] += 1


def health() -> dict:
    window = [r for r in RECENT if time.time() - r[0] < 15]
    if not window:
        return {"status": "healthy", "error_rate": 0.0, "latency_ms": None, "window": 0}
    errors = sum(1 for r in window if not r[1])
    rate = errors / len(window)
    latency = sum(r[2] for r in window) / len(window)
    status = "healthy" if rate == 0 else "degraded" if rate < 0.5 else "down"
    return {"status": status, "error_rate": round(rate, 3), "latency_ms": round(latency, 1), "window": len(window)}
