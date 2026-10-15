"""Missions: create, list, inspect, cancel, events, state, report."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from nexus.core.meter import meter
from nexus.core.services import services
from nexus.db import repo
from nexus.db.models import MissionRow

router = APIRouter(prefix="/missions", tags=["missions"])


class MissionCreate(BaseModel):
    task: str = Field(min_length=3, max_length=8000)
    title: str | None = None
    playbook: str | None = Field(default=None, description="Omit to let the Shogun decide.")
    inputs: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, int] | None = None


class MissionOut(BaseModel):
    id: str
    title: str
    task: str
    playbook: str | None
    status: str
    outcome: str | None
    source: str
    tokens: int
    error: str | None
    report: dict[str, Any] | None
    inputs: dict[str, Any]
    forked_from: str | None
    created_at: float
    updated_at: float


def out(row: MissionRow) -> MissionOut:
    return MissionOut.model_validate(row, from_attributes=True)


@router.post("", response_model=MissionOut, status_code=201)
async def create(body: MissionCreate) -> MissionOut:
    if body.playbook:
        from nexus.playbooks import all_playbooks

        if body.playbook not in {p.id for p in all_playbooks()}:
            raise HTTPException(422, f"unknown playbook '{body.playbook}'")
    row = await services().runner.create(
        body.task, title=body.title, playbook=body.playbook, inputs=body.inputs, limits=body.limits
    )
    return out(row)


@router.get("", response_model=list[MissionOut])
async def list_missions(limit: int = 50, status: str | None = None) -> list[MissionOut]:
    q = select(MissionRow).order_by(MissionRow.created_at.desc()).limit(min(limit, 200))
    if status:
        q = q.where(MissionRow.status == status)
    async with services().db.session() as s:
        return [out(r) for r in (await s.execute(q)).scalars()]


async def _mission(mission_id: str) -> MissionRow:
    row = await repo.get_mission(services().db, mission_id)
    if row is None:
        raise HTTPException(404, "mission not found")
    return row


@router.get("/{mission_id}", response_model=MissionOut)
async def get_mission(mission_id: str) -> MissionOut:
    return out(await _mission(mission_id))


@router.post("/{mission_id}/cancel")
async def cancel(mission_id: str) -> dict[str, bool]:
    await _mission(mission_id)
    return {"cancelled": await services().runner.cancel(mission_id)}


@router.get("/{mission_id}/events")
async def events(mission_id: str, after_seq: int = 0, limit: int = 2000) -> list[dict[str, Any]]:
    await _mission(mission_id)
    return await repo.events_after(services().db, mission_id, after_seq, min(limit, 10000))


@router.get("/{mission_id}/state")
async def state(mission_id: str) -> dict[str, Any]:
    await _mission(mission_id)
    runner = services().runner
    snap = await runner.graph.aget_state(runner.config(mission_id))
    usage = meter.usage(mission_id)
    return {
        "values": jsonable(snap.values),
        "next": list(snap.next),
        "checkpoint_id": (snap.config or {}).get("configurable", {}).get("checkpoint_id"),
        "interrupts": [jsonable(i.value) for i in snap.interrupts],
        "tokens": {
            "prompt": usage.prompt,
            "completion": usage.completion,
            "calls": usage.calls,
            "by_agent": dict(usage.by_agent),
        },
    }


@router.get("/{mission_id}/report")
async def report(mission_id: str) -> dict[str, Any]:
    row = await _mission(mission_id)
    if not row.report:
        raise HTTPException(409, f"mission is {row.status}; no report yet")
    return row.report


def jsonable(value: Any) -> Any:
    """State values may contain LangChain messages; make everything JSON-safe."""
    from langchain_core.messages import BaseMessage

    if isinstance(value, BaseMessage):
        return {"type": value.type, "name": value.name, "content": value.content}
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return str(value)
