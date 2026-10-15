"""Approval inbox and decisions from the UI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nexus.core.services import services
from nexus.db.models import ApprovalRow
from nexus.graph.runner import MissionNotPausedError
from nexus.graph.schemas import ApprovalDecision
from nexus.hitl.approvals import ApprovalError

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalOut(BaseModel):
    id: str
    mission_id: str
    kind: str
    status: str
    payload: dict[str, Any]
    decision: dict[str, Any] | None
    risk_level: str | None
    email_status: str | None
    created_at: float
    decided_at: float | None


def out(row: ApprovalRow) -> ApprovalOut:
    return ApprovalOut.model_validate(row, from_attributes=True)


@router.get("", response_model=list[ApprovalOut])
async def list_approvals(
    status: str | None = "pending", mission_id: str | None = None
) -> list[ApprovalOut]:
    rows = await services().approvals.list(status=status or None, mission_id=mission_id)
    return [out(r) for r in rows]


@router.get("/{approval_id}", response_model=ApprovalOut)
async def get_approval(approval_id: str) -> ApprovalOut:
    row = await services().approvals.get(approval_id)
    if row is None:
        raise HTTPException(404, "approval not found")
    return out(row)


@router.post("/{approval_id}/decide", response_model=ApprovalOut)
async def decide(approval_id: str, body: ApprovalDecision) -> ApprovalOut:
    decision = body.model_copy(
        update={"channel": "ui" if body.channel == "email" else body.channel}
    )
    try:
        row = await services().approvals.decide(approval_id, decision)
    except ApprovalError as exc:
        raise HTTPException(409, str(exc)) from exc
    except MissionNotPausedError as exc:
        raise HTTPException(409, str(exc)) from exc
    return out(row)
