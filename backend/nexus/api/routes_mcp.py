"""Tools: MCP servers, tools, health, call log and a "try tool" endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from nexus.core.services import services
from nexus.db.models import ToolCallRow

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/servers")
async def servers() -> list[dict[str, Any]]:
    hub = services().mcp
    health = await hub.health()
    return [{**s, "health": health.get(s["name"])} for s in hub.describe()]


@router.get("/calls")
async def calls(server: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    q = select(ToolCallRow).order_by(ToolCallRow.ts.desc()).limit(min(limit, 300))
    if server:
        q = q.where(ToolCallRow.server == server)
    async with services().db.session() as s:
        rows = (await s.execute(q)).scalars().all()
    return [
        {
            "id": r.id,
            "ts": r.ts,
            "tool": f"{r.server}.{r.tool}",
            "agent_id": r.agent_id,
            "mission_id": r.mission_id,
            "args": r.args,
            "ok": r.ok,
            "result": r.result[:1500],
            "duration_ms": r.duration_ms,
        }
        for r in rows
    ]


class TryTool(BaseModel):
    tool: str = Field(description="Qualified name, e.g. knowledge.search")
    args: dict[str, Any] = Field(default_factory=dict)
    workspace: str = "playground"


@router.post("/try")
async def try_tool(body: TryTool) -> dict[str, Any]:
    hub = services().mcp
    if body.tool not in hub.tools:
        raise HTTPException(404, f"unknown tool {body.tool}")
    if hub.tools[body.tool]["server"] == "notify":
        raise HTTPException(403, "notify tools need an approved mission action")
    outcome = await hub.call(
        body.tool, body.args, agent_id="playground", allowlist=None, workspace=body.workspace
    )
    return {
        "ok": outcome.ok,
        "text": outcome.text,
        "data": outcome.data,
        "duration_ms": outcome.duration_ms,
    }


@router.get("/sandbox")
async def sandbox_status() -> dict[str, Any]:
    return dict(await services().sandbox.status())
