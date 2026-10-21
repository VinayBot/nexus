"""Sliding-window rate limits stored in the database (``rate_hits``).

Limits survive restarts and are shared by every backend replica that uses the same
PostgreSQL. Two replicas racing on one key can overshoot by a request, which is fine for
abuse limits (they are not quotas of money).
"""

from __future__ import annotations

import time

from sqlalchemy import delete, func, select

from nexus.db.engine import Database
from nexus.db.models import RateHitRow


class RateLimiter:
    def __init__(self, name: str, limit: int, window_s: float) -> None:
        self.name = name
        self.limit = limit
        self.window_s = window_s

    def _key(self, key: str) -> str:
        return f"{self.name}:{key}"[:200]

    async def allow(self, db: Database, key: str, now: float | None = None) -> bool:
        """Count this request unless the window is full. Old hits are pruned as we go."""
        now = time.time() if now is None else now
        k = self._key(key)
        async with db.session() as s:
            await s.execute(
                delete(RateHitRow).where(RateHitRow.key == k, RateHitRow.ts <= now - self.window_s)
            )
            used = await s.scalar(select(func.count()).where(RateHitRow.key == k))
            if int(used or 0) >= self.limit:
                return False
            s.add(RateHitRow(key=k, ts=now))
        return True

    async def retry_after(self, db: Database, key: str, now: float | None = None) -> int:
        """Seconds until the oldest hit in the window expires."""
        now = time.time() if now is None else now
        async with db.session() as s:
            oldest = await s.scalar(
                select(func.min(RateHitRow.ts)).where(RateHitRow.key == self._key(key))
            )
        return int(self.window_s - (now - oldest)) + 1 if oldest is not None else 0
