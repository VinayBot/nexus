"""Prometheus metrics at ``GET /metrics`` (text exposition format 0.0.4).

Gauges are computed at scrape time from the database and the live services, so
there is no extra bookkeeping in the hot path: one grouped query per table.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select

from nexus import __version__
from nexus.core.services import services
from nexus.db.models import ApprovalRow, MissionRow, OutboxRow

router = APIRouter(tags=["observability"])


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _metric(
    name: str, kind: str, help_: str, samples: Iterable[tuple[dict[str, str], float]]
) -> list[str]:
    lines = [f"# HELP {name} {help_}", f"# TYPE {name} {kind}"]
    for labels, value in samples:
        label = ",".join(f'{k}="{_esc(v)}"' for k, v in labels.items())
        lines.append(f"{name}{{{label}}} {value:g}" if label else f"{name} {value:g}")
    return lines


@router.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
async def metrics() -> PlainTextResponse:
    svc = services()
    async with svc.db.session() as s:
        missions = (
            await s.execute(select(MissionRow.status, func.count()).group_by(MissionRow.status))
        ).all()
        tokens = await s.scalar(select(func.coalesce(func.sum(MissionRow.tokens), 0)))
        approvals = (
            await s.execute(select(ApprovalRow.status, func.count()).group_by(ApprovalRow.status))
        ).all()
        mail = (
            await s.execute(select(OutboxRow.status, func.count()).group_by(OutboxRow.status))
        ).all()
    gov = svc.governor.metrics()
    out: list[str] = []
    out += _metric("nexus_build_info", "gauge", "NEXUS version.", [({"version": __version__}, 1)])
    out += _metric(
        "nexus_missions",
        "gauge",
        "Missions by status.",
        [({"status": st}, n) for st, n in missions],
    )
    out += _metric(
        "nexus_tokens_total", "counter", "LLM tokens used by all missions.", [({}, tokens or 0)]
    )
    out += _metric(
        "nexus_approvals",
        "gauge",
        "Human approvals by status.",
        [({"status": st}, n) for st, n in approvals],
    )
    out += _metric(
        "nexus_emails",
        "gauge",
        "Emails by delivery status.",
        [({"status": st}, n) for st, n in mail],
    )
    out += _metric(
        "nexus_ram_available_bytes",
        "gauge",
        "Free RAM seen by the Resource Governor.",
        [({}, gov.ram_available_gb * 1e9)],
    )
    out += _metric(
        "nexus_llm_concurrency_limit",
        "gauge",
        "Concurrent LLM calls allowed right now (lowered under memory pressure).",
        [({"pressure": gov.pressure}, gov.limit)],
    )
    out += _metric("nexus_llm_in_flight", "gauge", "LLM calls running now.", [({}, gov.in_flight)])
    out += _metric(
        "nexus_llm_queue_depth", "gauge", "LLM calls waiting for a slot.", [({}, gov.queue_depth)]
    )
    out += _metric(
        "nexus_llm_tokens_per_second",
        "gauge",
        "Recent generation speed.",
        [({}, gov.tokens_per_sec)],
    )
    out += _metric(
        "nexus_circuit_open",
        "gauge",
        "1 when a model's circuit breaker is open.",
        [
            ({"key": str(b["key"])}, 1 if b["state"] == "open" else 0)
            for b in svc.breakers.snapshot()
        ],
    )
    return PlainTextResponse("\n".join(out) + "\n", media_type="text/plain; version=0.0.4")
