"""Hawk the Watcher: monitors the demo-service and opens incidents.

Polls ``/health`` every couple of seconds (emitting live ``service.health``
events), and when the service has been unhealthy for two consecutive polls with
no incident open, records an Incident (signal + recent error logs) and — if
auto-heal is on — starts a Self-Healing mission for it. An incident closes when
health returns to normal. The chaos switch that caused it is stored for the Fix
Library's bookkeeping but never shown to the agents.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from sqlalchemy import select

from nexus.core.event_types import AgentStatus, IncidentDetected, ServiceHealth
from nexus.core.events import emit
from nexus.core.logging import get_logger
from nexus.db import repo
from nexus.db.engine import Database
from nexus.db.models import IncidentRow
from nexus.graph.runner import MissionRunner
from nexus.playbooks.demo_service import DemoService

log = get_logger(__name__)
BACKOFF_S = 15 * 60
WAKE_GAP_S = 10.0  # polls are 2 s apart; a bigger gap means sleep or a stall
WAKE_GRACE_S = 20.0  # longer than the demo's 15 s health window


def error_digest(logs: list[dict[str, Any]], limit: int = 5) -> str:
    errors = [e for e in logs if e.get("level") == "ERROR"]
    lines = []
    seen: set[str] = set()
    for e in reversed(errors):
        key = f"{e.get('event')}:{e.get('message', '')[:80]}"
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"{e.get('event')}: {e.get('message')}")
        if e.get("traceback") and len(lines) <= 2:
            lines.append(e["traceback"][-1500:])
        if len(lines) >= limit:
            break
    return "\n".join(lines) or "(no error logs)"


class Watcher:
    def __init__(
        self, demo: DemoService, db: Database, runner: MissionRunner, *, auto_heal: bool = True
    ) -> None:
        self.demo = demo
        self.db = db
        self.runner = runner
        self.auto_heal = auto_heal
        self.last: dict[str, Any] = {"status": "unknown"}
        self._bad_streak = 0
        self._last_tick = 0.0
        self._grace_until = 0.0
        self.history: list[dict[str, Any]] = []

    async def open_incident(self) -> IncidentRow | None:
        async with self.db.session() as s:
            res = await s.execute(select(IncidentRow).where(IncidentRow.status == "open").limit(1))
            return res.scalars().first()

    async def tick(self, now: float | None = None) -> None:
        h = await self.demo.health()
        status = str(h.get("status", "down"))
        now = time.time() if now is None else now
        # A long gap between 2-second polls means the machine slept or stalled. On wake
        # every timer fires late, so the demo logs a burst of TimeoutErrors that are not a
        # bug. Ignore health until those orders leave the 15 s window (no false incidents).
        if self._last_tick and now - self._last_tick > WAKE_GAP_S:
            self._grace_until = now + WAKE_GRACE_S
            self._bad_streak = 0
            log.warning("watcher.wake_grace", gap_s=round(now - self._last_tick, 1))
        self._last_tick = now
        in_grace = now < self._grace_until
        self.last = {**h, "ts": time.time()}
        self.history = [
            *self.history[-299:],
            {
                "ts": self.last["ts"],
                "status": status,
                "error_rate": h.get("error_rate", 0),
                "latency_ms": h.get("latency_ms"),
            },
        ]
        emit(
            "service.health",
            ServiceHealth(
                service="demo",
                status=status if status in {"healthy", "degraded", "down"} else "down",
                error_rate=float(h.get("error_rate") or 0),
                latency_ms=h.get("latency_ms"),
            ),
        )
        incident = await self.open_incident()
        if status == "healthy":
            self._bad_streak = 0
            if incident is not None:
                async with self.db.session() as s:
                    row = await s.get(IncidentRow, incident.id)
                    if row is not None:
                        row.status = "resolved"
                log.info("incident.resolved", incident=incident.id)
            return
        if in_grace:
            return
        self._bad_streak += 1
        if self._bad_streak < 2 or incident is not None:
            return
        await self.raise_incident(status, h)

    async def raise_incident(self, status: str, h: dict[str, Any]) -> IncidentRow:
        logs = await self.demo.logs(80)
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"
        signal = f"demo-service {status}: error rate {float(h.get('error_rate') or 0):.0%}"
        row = IncidentRow(
            id=incident_id,
            service="demo",
            signal=signal,
            detail=error_digest(logs),
            chaos=",".join(self.demo.enabled()) or None,
            status="open",
        )
        async with self.db.session() as s:
            s.add(row)
        emit("agent.status", AgentStatus(agent_id="hawk", status="alarm"), agent_id="hawk")
        emit(
            "incident.detected",
            IncidentDetected(
                incident_id=incident_id, service="demo", signal=signal, detail=row.detail[:800]
            ),
        )
        log.warning("incident.detected", incident=incident_id, signal=signal)
        if self.auto_heal and await self.may_auto_heal():
            await self.heal(row)
        return row

    async def may_auto_heal(self) -> bool:
        """One automatic heal at a time, and a 15-minute back-off after a model outage.

        Without this, a flapping service on a starved machine queued heal after heal,
        each one failing on model timeouts.
        """
        # paused heals wait for a human and use no model time, so they do not block
        active = await repo.missions_with_status(self.db, ["queued", "running"])
        if any(m.source == "watcher" for m in active):
            log.warning("watcher.skip_heal", reason="a heal is already active")
            return False
        failed = await repo.missions_with_status(self.db, ["failed"])
        recent = [
            m
            for m in failed
            if m.source == "watcher"
            and "LLMUnavailableError" in (m.error or "")
            and time.time() - m.updated_at < BACKOFF_S
        ]
        if recent:
            log.warning("watcher.skip_heal", reason="model unavailable recently")
            return False
        return True

    async def heal(self, incident: IncidentRow) -> str:
        mission = await self.runner.create(
            f"Incident {incident.id}: {incident.signal}. Investigate the demo-service, reproduce the "
            "failure with a test, fix it safely, and verify the service is healthy again.",
            title=f"Heal {incident.id}: {incident.signal}"[:120],
            playbook="self_healing",
            inputs={"incident_id": incident.id},
            source="watcher",
        )
        async with self.db.session() as s:
            row = await s.get(IncidentRow, incident.id)
            if row is not None:
                row.mission_id = mission.id
        return mission.id

    async def run(self, interval_s: float = 2.0) -> None:
        await asyncio.sleep(3)  # let the service boot
        while True:
            try:
                await self.tick()
            except Exception as exc:  # noqa: BLE001 - the watcher loop must survive any single bad tick
                log.error("watcher.tick_failed", error=str(exc))
            await asyncio.sleep(interval_s)
