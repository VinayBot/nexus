"""Chaos Shrine: demo-service health, chaos switches (bells) and incidents."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from nexus.core.services import services
from nexus.db import repo
from nexus.db.models import IncidentRow
from nexus.playbooks.demo_service import SWITCHES

router = APIRouter(tags=["chaos"])


@router.get("/chaos")
async def chaos() -> dict[str, Any]:
    demo = services().demo
    enabled = set(demo.enabled())
    watcher = services().extras.get("watcher")
    return {
        "switches": [
            {
                "id": s.id,
                "title": s.title,
                "symptom": s.symptom,
                "file": s.file,
                "enabled": s.id in enabled,
            }
            for s in SWITCHES.values()
        ],
        "health": await demo.health(),
        "metrics": await demo.metrics(),
        "history": watcher.history[-120:] if watcher else [],
        "auto_heal": bool(watcher and watcher.auto_heal),
    }


class Toggle(BaseModel):
    enabled: bool


@router.post("/chaos/{switch_id}")
async def toggle(switch_id: str, body: Toggle) -> dict[str, Any]:
    if switch_id not in SWITCHES:
        raise HTTPException(404, "unknown switch")
    enabled = await services().demo.set_switch(switch_id, body.enabled)
    await repo.audit(
        services().db,
        actor="owner",
        channel="ui",
        action="chaos.toggle",
        detail={"switch": switch_id, "enabled": body.enabled},
    )
    return {"enabled": enabled}


@router.post("/chaos/reset")
async def reset() -> dict[str, str]:
    await services().demo.reset()
    return {"status": "baseline restored"}


class AutoHeal(BaseModel):
    enabled: bool


@router.put("/chaos/auto-heal")
async def auto_heal(body: AutoHeal) -> dict[str, bool]:
    watcher = services().extras.get("watcher")
    if watcher is None:
        raise HTTPException(409, "watcher not running")
    watcher.auto_heal = body.enabled
    return {"auto_heal": body.enabled}


@router.get("/demo/logs")
async def demo_logs(limit: int = 60, level: str | None = None) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = await services().demo.logs(min(limit, 300), level)
    return logs


@router.get("/incidents")
async def incidents(limit: int = 30) -> list[dict[str, Any]]:
    async with services().db.session() as s:
        rows = (
            await s.execute(select(IncidentRow).order_by(IncidentRow.ts.desc()).limit(limit))
        ).scalars()
        return [
            {
                "id": r.id,
                "ts": r.ts,
                "service": r.service,
                "signal": r.signal,
                "detail": r.detail[:2000],
                "status": r.status,
                "mission_id": r.mission_id,
            }
            for r in rows
        ]


@router.post("/incidents/{incident_id}/heal")
async def heal(incident_id: str) -> dict[str, str]:
    watcher = services().extras.get("watcher")
    async with services().db.session() as s:
        row = await s.get(IncidentRow, incident_id)
    if row is None or watcher is None:
        raise HTTPException(404, "incident or watcher not found")
    return {"mission_id": await watcher.heal(row)}
