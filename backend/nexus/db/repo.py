"""Small query helpers so routes and services do not hand-write SQL everywhere."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert

from nexus.core.events import Event
from nexus.db.engine import Database
from nexus.db.models import AgentStatRow, AuditRow, DeadLetterRow, EventRow, MissionRow


async def save_events(db: Database, events: list[Event]) -> None:
    rows = [
        {
            "id": e.id,
            "mission_id": e.mission_id,
            "seq": e.seq,
            "ts": e.ts,
            "type": e.type,
            "agent_id": e.agent_id,
            "node": e.node,
            "checkpoint_id": e.checkpoint_id,
            "payload": e.payload,
        }
        for e in events
        if e.mission_id
    ]
    if not rows:
        return
    async with db.session() as s:
        await s.execute(insert(EventRow).values(rows).on_conflict_do_nothing())


async def events_after(
    db: Database, mission_id: str, after_seq: int = 0, limit: int = 5000
) -> list[dict[str, Any]]:
    async with db.session() as s:
        res = await s.execute(
            select(EventRow)
            .where(EventRow.mission_id == mission_id, EventRow.seq > after_seq)
            .order_by(EventRow.seq)
            .limit(limit)
        )
        return [event_dict(r) for r in res.scalars()]


def event_dict(r: EventRow) -> dict[str, Any]:
    return {
        "id": r.id,
        "seq": r.seq,
        "mission_id": r.mission_id,
        "thread_id": r.mission_id,
        "checkpoint_id": r.checkpoint_id,
        "ts": r.ts,
        "agent_id": r.agent_id,
        "node": r.node,
        "type": r.type,
        "payload": r.payload,
    }


async def last_seq(db: Database, mission_id: str) -> int:
    async with db.session() as s:
        res = await s.execute(
            select(func.max(EventRow.seq)).where(EventRow.mission_id == mission_id)
        )
        return int(res.scalar() or 0)


async def get_mission(db: Database, mission_id: str) -> MissionRow | None:
    async with db.session() as s:
        return await s.get(MissionRow, mission_id)


async def update_mission(db: Database, mission_id: str, **values: Any) -> None:
    async with db.session() as s:
        await s.execute(update(MissionRow).where(MissionRow.id == mission_id).values(**values))


async def missions_with_status(db: Database, statuses: Sequence[str]) -> list[MissionRow]:
    async with db.session() as s:
        res = await s.execute(select(MissionRow).where(MissionRow.status.in_(statuses)))
        return list(res.scalars())


async def audit(
    db: Database,
    *,
    actor: str,
    channel: str,
    action: str,
    mission_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    async with db.session() as s:
        s.add(
            AuditRow(
                actor=actor,
                channel=channel,
                action=action,
                mission_id=mission_id,
                detail=detail or {},
            )
        )


async def dead_letter(
    db: Database, *, mission_id: str, node: str, error: str, checkpoint_id: str | None
) -> None:
    async with db.session() as s:
        s.add(
            DeadLetterRow(
                mission_id=mission_id, node=node, error=error, checkpoint_id=checkpoint_id
            )
        )


async def bump_agent_stats(db: Database, agent_id: str, **deltas: float) -> None:
    """Atomically add ``deltas`` to an agent's counters (row created on first use).

    Parallel workers can be the same agent, so this must be race-free: an upsert
    that ignores conflicts, then a single UPDATE with column increments.
    """
    defaults = {
        "agent_id": agent_id, "missions": 0, "steps": 0, "wins": 0, "tournaments": 0,
        "tests_passed": 0, "tests_run": 0, "retries": 0, "total_latency_ms": 0.0,
        "llm_calls": 0, "topics": {},
    }  # fmt: skip
    async with db.session() as s:
        await s.execute(insert(AgentStatRow).values(**defaults).on_conflict_do_nothing())
        if deltas:
            await s.execute(
                update(AgentStatRow)
                .where(AgentStatRow.agent_id == agent_id)
                .values({k: getattr(AgentStatRow, k) + v for k, v in deltas.items()})
            )


async def add_topic_reputation(db: Database, agent_id: str, topic: str, points: float) -> None:
    await bump_agent_stats(db, agent_id)
    async with db.session() as s:
        row = await s.get(AgentStatRow, agent_id)
        assert row is not None
        topics = dict(row.topics or {})
        topics[topic] = round(topics.get(topic, 0.0) + points, 2)
        row.topics = topics
