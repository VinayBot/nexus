"""Agent reputation: counters in ``agent_stats`` turned into leaderboard rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from nexus.core.logging import get_logger
from nexus.core.services import services
from nexus.db.models import AgentStatRow

log = get_logger(__name__)


async def agent_stats() -> dict[str, dict[str, Any]]:
    db = services().extras.get("db")
    if db is None:
        return {}
    async with db.session() as s:
        rows = (await s.execute(select(AgentStatRow))).scalars().all()
    return {
        r.agent_id: {
            "missions": r.missions,
            "steps": r.steps,
            "wins": r.wins,
            "tournaments": r.tournaments,
            "tests_passed": r.tests_passed,
            "tests_run": r.tests_run,
            "retries": r.retries,
            "llm_calls": r.llm_calls,
            "avg_latency_ms": round(r.total_latency_ms / r.steps, 1) if r.steps else 0.0,
            "test_pass_rate": round(r.tests_passed / r.tests_run, 3) if r.tests_run else None,
            "win_rate": round(r.wins / r.tournaments, 3) if r.tournaments else None,
            "topics": r.topics or {},
            "reputation": round(
                r.wins * 2
                + sum((r.topics or {}).values())
                + r.tests_passed * 0.2
                - r.retries * 0.1,
                2,
            ),
        }
        for r in rows
    }


async def bump(agent_id: str, **deltas: float) -> None:
    db = services().extras.get("db")
    if db is None:
        return
    from nexus.db.repo import bump_agent_stats

    try:
        await bump_agent_stats(db, agent_id, **deltas)
    except Exception as exc:  # bookkeeping must never fail a mission
        log.warning("reputation.bump_failed", agent=agent_id, error=str(exc))


async def reward(agent_id: str, topic: str, points: float) -> None:
    db = services().extras.get("db")
    if db is None:
        return
    from nexus.db.repo import add_topic_reputation

    try:
        await add_topic_reputation(db, agent_id, topic, points)
    except Exception as exc:
        log.warning("reputation.reward_failed", agent=agent_id, error=str(exc))
