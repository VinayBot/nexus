"""Observatory, Benchmarks (evals), Under the Hood, Settings and Curriculum evidence."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from nexus.core.logging import LOG_BUFFER
from nexus.core.services import services
from nexus.db.models import EvalRunRow, EventRow, MissionRow, TraceSpanRow
from nexus.evals import harness
from nexus.evals.lab import compare
from nexus.llm.demo_tools import COMPARE_TASKS

router = APIRouter(tags=["insight"])

#: Illustrative cloud prices (USD per 1M tokens) for the "what it would have cost" estimate.
CLOUD_PRICE = {"input": 3.0, "output": 15.0}


# --- observability -----------------------------------------------------------------------
@router.get("/observability/traces")
async def traces(mission_id: str) -> list[dict[str, Any]]:
    async with services().db.session() as s:
        rows = (
            await s.execute(
                select(TraceSpanRow)
                .where(TraceSpanRow.mission_id == mission_id)
                .order_by(TraceSpanRow.start)
                .limit(3000)
            )
        ).scalars()
        return [
            {
                "span_id": r.span_id,
                "trace_id": r.trace_id,
                "parent_id": r.parent_id,
                "name": r.name,
                "kind": r.kind,
                "start": r.start,
                "end": r.end,
                "status": r.status,
                "attributes": r.attributes,
            }
            for r in rows
        ]


@router.get("/observability/summary")
async def summary(limit: int = 20) -> dict[str, Any]:
    db = services().db
    async with db.session() as s:
        missions = (
            (
                await s.execute(
                    select(MissionRow).order_by(MissionRow.created_at.desc()).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        ids = [m.id for m in missions]
        counts = dict(
            (
                await s.execute(
                    select(EventRow.type, func.count())
                    .where(EventRow.mission_id.in_(ids))
                    .group_by(EventRow.type)
                )
            ).all()
        )
        calls = (
            await s.execute(
                select(EventRow.payload, EventRow.mission_id).where(
                    EventRow.mission_id.in_(ids), EventRow.type == "llm.call"
                )
            )
        ).all()
        routed = (
            (
                await s.execute(
                    select(EventRow.payload)
                    .where(EventRow.mission_id.in_(ids), EventRow.type == "llm.routed")
                    .order_by(EventRow.ts.desc())
                    .limit(40)
                )
            )
            .scalars()
            .all()
        )
        retries = (
            (
                await s.execute(
                    select(EventRow.payload).where(
                        EventRow.mission_id.in_(ids), EventRow.type == "retry"
                    )
                )
            )
            .scalars()
            .all()
        )
    per_mission: dict[str, dict[str, float]] = {}
    by_purpose: dict[str, dict[str, float]] = {}
    for payload, mid in calls:
        pm = per_mission.setdefault(mid, {"prompt": 0, "completion": 0, "calls": 0, "llm_ms": 0})
        pm["prompt"] += payload["prompt_tokens"]
        pm["completion"] += payload["completion_tokens"]
        pm["calls"] += 1
        pm["llm_ms"] += payload["duration_ms"]
        bp = by_purpose.setdefault(
            payload["purpose"].split(":")[0], {"calls": 0, "tokens": 0, "ms": 0}
        )
        bp["calls"] += 1
        bp["tokens"] += payload["prompt_tokens"] + payload["completion_tokens"]
        bp["ms"] += payload["duration_ms"]
    retry_layers: dict[str, int] = {}
    for r in retries:
        retry_layers[r["layer"]] = retry_layers.get(r["layer"], 0) + 1
    rows = []
    for m in missions:
        pm = per_mission.get(m.id, {"prompt": 0, "completion": 0, "calls": 0, "llm_ms": 0})
        cost = (
            pm["prompt"] / 1e6 * CLOUD_PRICE["input"]
            + pm["completion"] / 1e6 * CLOUD_PRICE["output"]
        )
        rows.append(
            {
                "id": m.id,
                "title": m.title,
                "playbook": m.playbook,
                "status": m.status,
                "outcome": m.outcome,
                "duration_s": round(m.updated_at - m.created_at, 1),
                **pm,
                "cloud_cost_usd": round(cost, 4),
            }
        )
    return {
        "missions": rows,
        "event_counts": counts,
        "by_purpose": {
            k: {**v, "avg_ms": round(v["ms"] / v["calls"])} for k, v in by_purpose.items()
        },
        "retries": retry_layers,
        "routing": routed,
        "circuits": services().breakers.snapshot(),
        "governor": list(services().governor.history)[-300:],
        "cloud_price": CLOUD_PRICE,
    }


@router.get("/observability/logs")
async def logs(
    level: str | None = None, contains: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    out = list(LOG_BUFFER)
    if level:
        out = [r for r in out if r["level"] == level.lower()]
    if contains:
        out = [r for r in out if contains.lower() in (r["event"] + str(r["fields"])).lower()]
    return out[-limit:]


# --- evals ------------------------------------------------------------------------------
@router.get("/evals/suites")
async def suites() -> list[dict[str, str]]:
    return [{"id": k, "title": v[0]} for k, v in harness.SUITES.items()]


@router.post("/evals/{suite}/run", status_code=202)
async def run_suite(suite: str) -> dict[str, str]:
    try:
        run_id = await harness.start(suite)
    except KeyError as exc:
        raise HTTPException(404, "unknown suite") from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"run_id": run_id}


@router.get("/evals/runs")
async def runs(suite: str | None = None) -> list[dict[str, Any]]:
    q = select(EvalRunRow).order_by(EvalRunRow.started_at.desc()).limit(50)
    if suite:
        q = q.where(EvalRunRow.suite == suite)
    async with services().db.session() as s:
        return [
            {
                "id": r.id,
                "suite": r.suite,
                "status": r.status,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
                "model": r.model,
                "summary": r.summary,
                "cases": r.cases,
            }
            for r in (await s.execute(q)).scalars()
        ]


# --- under the hood ---------------------------------------------------------------------
class LabRequest(BaseModel):
    task: str = Field(default=COMPARE_TASKS[0], min_length=3, max_length=500)


@router.get("/lab/tasks")
async def lab_tasks() -> list[str]:
    return COMPARE_TASKS


@router.post("/lab/compare")
async def lab_compare(body: LabRequest) -> dict[str, Any]:
    return await compare(body.task)


# --- settings ---------------------------------------------------------------------------
class SettingsPatch(BaseModel):
    llm_max_concurrency: int | None = Field(default=None, ge=1, le=8)
    pruning_strategy: Literal["sliding_window", "summarise"] | None = None
    verify_window_s: float | None = Field(default=None, ge=2, le=120)
    auto_heal: bool | None = None


def _settings_view() -> dict[str, Any]:
    st = services().settings
    watcher = services().extras.get("watcher")
    return {
        "model_profile": services().extras.get("model_profile", st.model_profile.value),
        "models": services().llm.router.models.model_dump(),
        "fallback_model": services().llm.fallback_model,
        "num_ctx": st.num_ctx,
        "llm_max_concurrency": services().governor.configured_limit,
        "llm_timeout_s": st.llm_timeout_s,
        "pruning_strategy": st.pruning_strategy,
        "verify_window_s": st.verify_window_s,
        "auto_heal": bool(watcher.auto_heal) if watcher else st.auto_heal,
        "mission_token_limit": services().policies.token_cap(st.mission_token_limit),
        "sandbox_backend": st.sandbox_backend,
        "smtp": f"{st.smtp_host}:{st.smtp_port}",
        "owner_email": st.owner_email,
        "public_url": st.public_url,
        "ollama_base_url": st.ollama_base_url,
        "default_secret": st.secret_key == "dev-only-change-me",
    }


@router.get("/settings")
async def get_settings_view() -> dict[str, Any]:
    return _settings_view()


@router.put("/settings")
async def put_settings(body: SettingsPatch) -> dict[str, Any]:
    st = services().settings
    if body.llm_max_concurrency is not None:
        services().governor.set_limit(body.llm_max_concurrency)
    if body.pruning_strategy is not None:
        st.pruning_strategy = body.pruning_strategy
    if body.verify_window_s is not None:
        st.verify_window_s = body.verify_window_s
    if body.auto_heal is not None:
        st.auto_heal = body.auto_heal
        watcher = services().extras.get("watcher")
        if watcher is not None:
            watcher.auto_heal = body.auto_heal
    return _settings_view()


# --- curriculum evidence -------------------------------------------------------------------
@router.get("/curriculum/evidence")
async def evidence() -> dict[str, int]:
    """How often each concept's tell-tale event has really happened (all missions)."""
    async with services().db.session() as s:
        counts = dict(
            (await s.execute(select(EventRow.type, func.count()).group_by(EventRow.type))).all()
        )
        forks = counts.get("timetravel.fork", 0)
    return {str(k): int(v) for k, v in counts.items()} | {"timetravel.fork": int(forks)}
