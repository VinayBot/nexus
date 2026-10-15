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
from nexus.db.engine import Database
from nexus.db.models import IncidentRow
from nexus.graph.runner import MissionRunner
from nexus.playbooks.demo_service import DemoService

log = get_logger(__name__)


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
        self.history: list[dict[str, Any]] = []

    async def open_incident(self) -> IncidentRow | None:
        async with self.db.session() as s:
            res = await s.execute(select(IncidentRow).where(IncidentRow.status == "open").limit(1))
            return res.scalars().first()

    async def tick(self) -> None:
        h = await self.demo.health()
        status = str(h.get("status", "down"))
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
        if self.auto_heal:
            await self.heal(row)
        return row

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
            except Exception as exc:
                log.error("watcher.tick_failed", error=str(exc))
            await asyncio.sleep(interval_s)
