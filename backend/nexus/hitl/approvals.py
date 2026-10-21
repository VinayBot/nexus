"""Approvals: interrupts become inbox items; decisions resume the paused graph.

A decision can arrive from the UI, the API or a signed email link. Whatever the
channel, it is validated, written to the audit log, emitted as
``interrupt.resolved`` and passed to LangGraph as ``Command(resume=decision)``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select

from nexus.core.event_types import InterruptRaised, InterruptResolved
from nexus.core.events import emit
from nexus.db import repo
from nexus.db.engine import Database
from nexus.db.models import ApprovalRow
from nexus.graph.runner import MissionRunner
from nexus.graph.schemas import ApprovalDecision

STATUS_FOR = {"approve": "approved", "reject": "rejected", "edit": "edited", "respond": "responded"}


class ApprovalError(RuntimeError):
    pass


class ApprovalService:
    def __init__(self, db: Database, runner: MissionRunner) -> None:
        self.db = db
        self.runner = runner
        #: called after a new approval is recorded (e.g. send the approval email)
        self.on_new: list[Callable[[ApprovalRow], Awaitable[None]]] = []
        runner.interrupt_hooks.append(self.record)

    async def record(self, mission_id: str, value: dict[str, Any]) -> None:
        approval_id = str(value.get("approval_id") or f"{mission_id}-{int(time.time())}")
        async with self.db.session() as s:
            existing = await s.get(ApprovalRow, approval_id)
            if existing is not None:
                return  # same interrupt re-surfaced after a restart
            row = ApprovalRow(
                id=approval_id,
                mission_id=mission_id,
                kind=str(value.get("kind", "approve_action")),
                status="pending",
                payload=value,
                risk_level=(value.get("risk") or {}).get("level"),
            )
            s.add(row)
        emit(
            "interrupt.raised",
            InterruptRaised(
                kind=row.kind,
                approval_id=approval_id,
                summary=str(value.get("summary", ""))[:500],
                risk_level=row.risk_level,
            ),
            mission_id=mission_id,
        )
        for hook in self.on_new:
            await hook(row)

    async def get(self, approval_id: str) -> ApprovalRow | None:
        async with self.db.session() as s:
            return await s.get(ApprovalRow, approval_id)

    async def list(
        self, status: str | None = "pending", mission_id: str | None = None
    ) -> list[ApprovalRow]:
        q = select(ApprovalRow).order_by(ApprovalRow.created_at.desc())
        if status:
            q = q.where(ApprovalRow.status == status)
        if mission_id:
            q = q.where(ApprovalRow.mission_id == mission_id)
        async with self.db.session() as s:
            return list((await s.execute(q.limit(200))).scalars())

    async def decide(self, approval_id: str, decision: ApprovalDecision) -> ApprovalRow:
        async with self.db.session() as s:
            row = await s.get(ApprovalRow, approval_id)
            if row is None:
                raise ApprovalError("unknown approval")
            if row.status != "pending":
                raise ApprovalError(f"approval already {row.status}")
            if (
                row.payload.get("requires_override")
                and decision.decision == "approve"
                and "override" not in decision.reason.lower()
            ):
                raise ApprovalError("CRITICAL action: approval must state 'override' in the reason")
            row.status = STATUS_FOR[decision.decision]
            row.decision = decision.model_dump()
            row.decided_at = time.time()
            mission_id = row.mission_id
        await repo.audit(
            self.db,
            actor=decision.by,
            channel=decision.channel,
            action=f"approval.{decision.decision}",
            mission_id=mission_id,
            detail={"approval_id": approval_id, "kind": row.kind, **decision.model_dump()},
        )
        emit(
            "interrupt.resolved",
            InterruptResolved(
                approval_id=approval_id,
                decision=decision.decision,
                by=decision.by,
                channel=decision.channel,
            ),
            mission_id=mission_id,
        )
        try:
            await self.runner.resume(mission_id, decision.model_dump())
        except Exception as exc:  # undo the decision whatever made the resume fail
            # never leave an approval "decided" for a mission that did not resume
            async with self.db.session() as s:
                fresh = await s.get(ApprovalRow, approval_id)
                if fresh is not None:
                    fresh.status, fresh.decision, fresh.decided_at = "pending", None, None
            raise ApprovalError(f"could not resume the mission: {exc}") from exc
        return row
