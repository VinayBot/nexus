"""Email approvals, time travel, audit log, dead letters and policies."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from nexus.api.schemas import AuditEntry, CheckpointState, DeadLetter, RunStatus
from nexus.core.services import services
from nexus.db import repo
from nexus.db.models import AuditRow, DeadLetterRow, OutboxRow
from nexus.hitl.timetravel import TimeTravelError
from nexus.safety.policies import Policy

router = APIRouter(tags=["hitl"])


# --- email approval links ---------------------------------------------------------------
@router.get("/approvals/email/{token}", response_class=HTMLResponse)
async def email_confirm(token: str) -> HTMLResponse:
    code, body = await services().email_approvals.confirm_page(token)
    return HTMLResponse(body, status_code=code)


@router.post("/approvals/email/{token}", response_class=HTMLResponse)
async def email_decide(token: str, reason: str = Form("")) -> HTMLResponse:
    code, body = await services().email_approvals.decide(token, reason)
    return HTMLResponse(body, status_code=code)


@router.get("/outbox")
async def outbox(limit: int = 30) -> list[dict[str, Any]]:
    async with services().db.session() as s:
        rows = (
            await s.execute(select(OutboxRow).order_by(OutboxRow.ts.desc()).limit(limit))
        ).scalars()
        return [
            {
                "id": r.id,
                "ts": r.ts,
                "to": r.to,
                "subject": r.subject,
                "status": r.status,
                "mission_id": r.mission_id,
            }
            for r in rows
        ]


# --- time travel ---------------------------------------------------------------------------
def _tt() -> Any:
    return services().timetravel


@router.get("/missions/{mission_id}/history")
async def history(mission_id: str) -> dict[str, Any]:
    result: dict[str, Any] = await _tt().history(mission_id)
    return result


@router.get("/missions/{mission_id}/checkpoints/{checkpoint_id}")
async def checkpoint(mission_id: str, checkpoint_id: str) -> CheckpointState:
    from nexus.api.routes_missions import jsonable

    try:
        data = await _tt().state_at(mission_id, checkpoint_id)
    except TimeTravelError as exc:
        raise HTTPException(404, str(exc)) from exc
    return CheckpointState(summary=data["summary"], values=jsonable(data["values"]))


class Rerun(BaseModel):
    checkpoint_id: str


@router.post("/missions/{mission_id}/rerun")
async def rerun(mission_id: str, body: Rerun) -> RunStatus:
    try:
        await _tt().rerun(mission_id, body.checkpoint_id)
    except TimeTravelError as exc:
        raise HTTPException(409, str(exc)) from exc
    return RunStatus(status="running")


class Fork(BaseModel):
    checkpoint_id: str
    patch: dict[str, Any] = Field(default_factory=dict, description="State keys to overwrite")
    as_node: str | None = Field(default=None, description="Pretend this node wrote the patch")
    label: str | None = None
    run: bool = True


@router.post("/missions/{mission_id}/fork")
async def fork(mission_id: str, body: Fork) -> dict[str, Any]:
    try:
        result: dict[str, Any] = await _tt().fork(
            mission_id,
            body.checkpoint_id,
            body.patch,
            as_node=body.as_node,
            label=body.label,
            run=body.run,
        )
    except TimeTravelError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:  # invalid patch for the graph
        raise HTTPException(422, f"fork failed: {exc}") from exc
    return result


@router.post("/missions/{mission_id}/runner-up")
async def runner_up(mission_id: str) -> dict[str, Any]:
    try:
        result: dict[str, Any] = await _tt().choose_runner_up(mission_id)
    except TimeTravelError as exc:
        raise HTTPException(409, str(exc)) from exc
    return result


@router.get("/missions/{mission_id}/compare")
async def compare(mission_id: str, a: str, b: str) -> dict[str, Any]:
    try:
        result: dict[str, Any] = await _tt().compare(mission_id, a, b)
    except TimeTravelError as exc:
        raise HTTPException(404, str(exc)) from exc
    return result


# --- audit, dead letters ---------------------------------------------------------------------
@router.get("/audit")
async def audit(mission_id: str | None = None, limit: int = 100) -> list[AuditEntry]:
    q = select(AuditRow).order_by(AuditRow.ts.desc()).limit(min(limit, 500))
    if mission_id:
        q = q.where(AuditRow.mission_id == mission_id)
    async with services().db.session() as s:
        return [
            AuditEntry.model_validate(r, from_attributes=True)
            for r in (await s.execute(q)).scalars()
        ]


@router.get("/dead-letters")
async def dead_letters(include_resolved: bool = False) -> list[DeadLetter]:
    q = select(DeadLetterRow).order_by(DeadLetterRow.created_at.desc()).limit(100)
    if not include_resolved:
        q = q.where(DeadLetterRow.resolved.is_(False))
    async with services().db.session() as s:
        return [
            DeadLetter.model_validate(r, from_attributes=True)
            for r in (await s.execute(q)).scalars()
        ]


@router.post("/dead-letters/{letter_id}/retry")
async def retry_dead_letter(letter_id: int) -> dict[str, str]:
    """ "Retry from here": continue the failed mission from its last good checkpoint."""
    async with services().db.session() as s:
        row = await s.get(DeadLetterRow, letter_id)
        if row is None:
            raise HTTPException(404, "not found")
        mission_id, checkpoint_id = row.mission_id, row.checkpoint_id
        row.resolved = True
    runner = services().runner
    if runner.is_running(mission_id):
        raise HTTPException(409, "mission already running")
    await repo.audit(
        services().db,
        actor="owner",
        channel="ui",
        action="dead_letter.retry",
        mission_id=mission_id,
        detail={"letter": letter_id},
    )
    runner.start(mission_id, None, resumed=True, checkpoint_id=checkpoint_id)
    return {"status": "running", "mission_id": mission_id}


# --- policies ----------------------------------------------------------------------------
@router.get("/policies")
async def get_policies() -> list[dict[str, Any]]:
    return [p.model_dump() for p in services().policies.policies]


@router.put("/policies")
async def put_policies(body: list[Policy]) -> list[dict[str, Any]]:
    services().policies.save(body)
    await repo.audit(
        services().db,
        actor="owner",
        channel="ui",
        action="policies.update",
        detail={"count": len(body)},
    )
    return [p.model_dump() for p in services().policies.policies]
