"""Tickets, uploads, project downloads, saved playbooks, agent registry and reputation."""

from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from nexus.agents.registry import AgentSpec
from nexus.agents.reputation import agent_stats
from nexus.core.services import services
from nexus.db import repo
from nexus.db.models import TicketRow
from nexus.playbooks import reload_saved
from nexus.playbooks.dynamic import SavedPlaybookSpec, save_playbook

router = APIRouter(tags=["work"])

MAX_UPLOAD = 2_000_000


# --- tickets ----------------------------------------------------------------------------
@router.get("/tickets")
async def tickets() -> list[dict[str, Any]]:
    async with services().db.session() as s:
        rows = (await s.execute(select(TicketRow).order_by(TicketRow.id))).scalars()
        return [
            {
                "id": t.id,
                "title": t.title,
                "body": t.body,
                "status": t.status,
                "labels": t.labels,
                "comments": t.comments,
                "attachments": [
                    {"name": a["name"], "size": len(a.get("content", "")), "ts": a.get("ts")}
                    for a in t.attachments
                ],
            }
            for t in rows
        ]


class TicketIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=3, max_length=8000)
    labels: list[str] = Field(default_factory=list)


@router.post("/tickets", status_code=201)
async def create_ticket(body: TicketIn) -> dict[str, str]:
    async with services().db.session() as s:
        n = len((await s.execute(select(TicketRow.id))).all())
        tid = f"T-{201 + n}"
        s.add(
            TicketRow(
                id=tid,
                title=body.title,
                body=body.body,
                labels=body.labels,
                comments=[],
                attachments=[],
            )
        )
    return {"id": tid}


@router.get("/tickets/{ticket_id}/attachments/{name}")
async def attachment(ticket_id: str, name: str) -> dict[str, Any]:
    async with services().db.session() as s:
        t = await s.get(TicketRow, ticket_id)
    if t is None:
        raise HTTPException(404, "ticket not found")
    for a in t.attachments:
        if a["name"] == name:
            return {"name": name, "content": a["content"]}
    raise HTTPException(404, "attachment not found")


# --- uploads (Project Builder docs) --------------------------------------------------------
@router.post("/uploads/parse")
async def parse_upload(file: UploadFile = File(...)) -> dict[str, Any]:  # noqa: B008
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "file too large (2 MB max)")
    name = file.filename or "upload"
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:40])
    elif suffix in {".md", ".txt", ".markdown", ".rst", ".json", ".yaml", ".yml"}:
        text = data.decode("utf-8", errors="replace")
    else:
        raise HTTPException(415, "supported: .pdf, .md, .txt")
    return {"name": name, "chars": len(text), "text": text[:60_000]}


@router.get("/missions/{mission_id}/download")
async def download(mission_id: str) -> FileResponse:
    path = services().settings.data_dir / "exports" / f"{mission_id}.zip"
    if not path.is_file():
        raise HTTPException(404, "no package for this mission (not built or not approved yet)")
    return FileResponse(path, filename=f"nexus-{mission_id}.zip", media_type="application/zip")


# --- saved playbooks ---------------------------------------------------------------------
class SaveRequest(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,40}$")
    title: str
    description: str


@router.post("/playbooks/from-mission/{mission_id}", status_code=201)
async def save_from_mission(mission_id: str, body: SaveRequest) -> dict[str, str]:
    row = await repo.get_mission(services().db, mission_id)
    if row is None or row.outcome != "success":
        raise HTTPException(409, "only successful missions can become playbooks")
    runner = services().runner
    state = (await runner.graph.aget_state(runner.config(mission_id))).values
    if not state.get("plan"):
        raise HTTPException(409, "mission has no plan")
    spec = SavedPlaybookSpec(
        id=body.id,
        title=body.title,
        description=body.description,
        plan=state["plan"],
        source_mission=mission_id,
    )
    path = save_playbook(services().settings.data_dir / "playbooks", spec)
    reload_saved()
    await repo.audit(
        services().db,
        actor="owner",
        channel="ui",
        action="playbook.save",
        mission_id=mission_id,
        detail={"id": body.id},
    )
    return {"id": body.id, "path": str(path.name)}


# --- agent registry + reputation ------------------------------------------------------------
@router.get("/agents")
async def agents() -> list[dict[str, Any]]:
    stats = await agent_stats()
    return [{**a.model_dump(), "stats": stats.get(a.id)} for a in services().registry.all()]


@router.put("/agents/{agent_id}")
async def upsert_agent(agent_id: str, spec: AgentSpec) -> dict[str, Any]:
    if spec.id != agent_id:
        raise HTTPException(422, "id mismatch")
    saved: AgentSpec = services().registry.save(spec)
    await repo.audit(
        services().db, actor="owner", channel="ui", action="agent.save", detail={"id": agent_id}
    )
    return saved.model_dump()


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str) -> dict[str, str]:
    services().registry.delete(agent_id)
    return {"status": "reverted to built-in (or removed)"}


@router.get("/reputation")
async def reputation() -> list[dict[str, Any]]:
    stats = await agent_stats()
    rows = [
        {"agent_id": a.id, "name": a.name, "role": a.role, **(stats.get(a.id) or {"reputation": 0})}
        for a in services().registry.all()
    ]
    return sorted(rows, key=lambda r: r.get("reputation", 0), reverse=True)


class Playground(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@router.post("/agents/{agent_id}/playground")
async def playground(agent_id: str, body: Playground) -> dict[str, Any]:
    """Run one ReAct worker turn-loop for an agent outside any mission."""
    from nexus.graph.subgraphs.react_worker import initial_worker_state, react_worker

    spec = services().registry.get(agent_id)
    started = time.perf_counter()
    out = await react_worker.ainvoke(
        initial_worker_state(spec, body.message, spec.tools), {"recursion_limit": 40}
    )
    return {
        "answer": out.get("final"),
        "iterations": out.get("iteration"),
        "sources": out.get("sources"),
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }
