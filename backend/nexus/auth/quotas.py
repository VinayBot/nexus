"""Per-user limits on starting missions: a rate (missions per minute) and a daily
token quota. Both protect a single local machine from one runaway client or user.

Who started a mission is stored in ``inputs.created_by`` (set by the API).
"""

from __future__ import annotations

import time

from fastapi import HTTPException
from sqlalchemy import func, select

from nexus.auth.ratelimit import RateLimiter
from nexus.core.services import services
from nexus.db.models import MissionRow

DAY_S = 86_400


async def tokens_today(username: str) -> int:
    async with services().db.session() as s:
        total = await s.scalar(
            select(func.coalesce(func.sum(MissionRow.tokens), 0)).where(
                MissionRow.inputs["created_by"].as_string() == username,
                MissionRow.created_at >= time.time() - DAY_S,
            )
        )
    return int(total or 0)


async def check_mission_quota(username: str) -> None:
    """Raise 429 (with Retry-After) when this user may not start another mission now."""
    settings = services().settings
    db = services().db
    limiter = RateLimiter("missions", limit=settings.missions_per_minute, window_s=60)
    if not await limiter.allow(db, username):
        raise HTTPException(
            429,
            f"Too many missions: at most {settings.missions_per_minute} per minute.",
            headers={"Retry-After": str(await limiter.retry_after(db, username))},
        )
    quota = settings.daily_token_quota
    if quota and (used := await tokens_today(username)) >= quota:
        raise HTTPException(
            429,
            f"Daily token quota reached ({used:,} of {quota:,} tokens in 24 hours).",
            headers={"Retry-After": "3600"},
        )
