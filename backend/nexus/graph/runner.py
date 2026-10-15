"""Mission runner: drives the compiled graph for each mission (one thread per mission).

* Every super-step is checkpointed by ``AsyncSqliteSaver``; the runner turns each
  checkpoint into a ``checkpoint.saved`` event and stamps later events with it.
* When the graph pauses on ``interrupt()``, pending approvals are recorded and
  ``interrupt.raised`` is emitted; ``resume()`` continues with ``Command(resume=…)``.
* On startup ``recover()`` re-invokes every mission that was running when the
  process died — LangGraph continues from the last checkpoint, and already
  finished parallel tasks of that super-step are not re-run (pending writes).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from nexus.core.event_types import (
    CheckpointSaved,
    MissionCancelled,
    MissionCompleted,
    MissionCreated,
    MissionFailed,
    MissionStarted,
)
from nexus.core.events import MissionContext, bus, emit, mission_context
from nexus.core.logging import get_logger
from nexus.core.meter import meter
from nexus.core.tracing import span
from nexus.db import repo
from nexus.db.engine import Database
from nexus.db.models import MissionRow
from nexus.graph.instrument import last_failure

log = get_logger(__name__)

InterruptHook = Callable[[str, dict[str, Any]], Awaitable[None]]


class MissionNotPausedError(RuntimeError):
    pass


class MissionRunner:
    def __init__(
        self,
        graph: CompiledStateGraph[Any, Any, Any, Any],
        db: Database,
        *,
        token_cap: int = 120_000,
    ) -> None:
        self.graph = graph
        self.db = db
        self.token_cap = token_cap
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._shutting_down = False
        self.interrupt_hooks: list[InterruptHook] = []
        self.completion_hooks: list[Callable[[str, dict[str, Any]], Awaitable[None]]] = []

    # -- config ---------------------------------------------------------------------
    @staticmethod
    def config(mission_id: str, checkpoint_id: str | None = None) -> RunnableConfig:
        configurable: dict[str, Any] = {"thread_id": mission_id}
        if checkpoint_id:
            configurable["checkpoint_id"] = checkpoint_id
            configurable["checkpoint_ns"] = ""  # root graph namespace (needed by update_state)
        return {"configurable": configurable, "recursion_limit": 250}

    def is_running(self, mission_id: str) -> bool:
        t = self._tasks.get(mission_id)
        return t is not None and not t.done()

    # -- lifecycle --------------------------------------------------------------------
    async def create(
        self,
        task: str,
        *,
        title: str | None = None,
        playbook: str | None = None,
        inputs: dict[str, Any] | None = None,
        source: str = "ui",
        limits: dict[str, int] | None = None,
    ) -> MissionRow:
        mission_id = uuid.uuid4().hex[:12]
        inputs = {**(inputs or {}), "started_at": time.time()}
        if playbook:
            inputs["playbook"] = playbook
        row = MissionRow(
            id=mission_id,
            title=(title or task.strip().splitlines()[0])[:200],
            task=task,
            playbook=playbook,
            status="queued",
            source=source,
            inputs=inputs,
            tokens=0,
        )
        async with self.db.session() as s:
            s.add(row)
        emit(
            "mission.created",
            MissionCreated(title=row.title, playbook=playbook, task=task[:500]),
            mission_id=mission_id,
        )
        initial = {
            "mission_id": mission_id,
            "task": task,
            "title": row.title,
            "inputs": inputs,
            **({"limits": limits} if limits else {}),
        }
        self.start(mission_id, initial)
        return row

    def start(
        self,
        mission_id: str,
        payload: Any,
        *,
        resumed: bool = False,
        checkpoint_id: str | None = None,
    ) -> asyncio.Task[None]:
        if self.is_running(mission_id):
            raise RuntimeError(f"mission {mission_id} is already running")
        task = asyncio.create_task(
            self._drive(mission_id, payload, resumed=resumed, checkpoint_id=checkpoint_id),
            name=f"mission:{mission_id}",
        )
        self._tasks[mission_id] = task
        return task

    async def wait(self, mission_id: str) -> None:
        task = self._tasks.get(mission_id)
        if task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _drive(
        self, mission_id: str, payload: Any, *, resumed: bool, checkpoint_id: str | None
    ) -> None:
        ctx = MissionContext(mission_id=mission_id, thread_id=mission_id)
        token = mission_context.set(ctx)
        bus.prime(mission_id, await repo.last_seq(self.db, mission_id))
        meter.set_cap(mission_id, self.token_cap)
        await repo.update_mission(self.db, mission_id, status="running", error=None)
        emit("mission.started", MissionStarted(resumed=resumed))
        config = self.config(mission_id, checkpoint_id)
        root = span("mission", "mission", resumed=resumed)
        root.__enter__()
        try:
            async for chunk in self.graph.astream(payload, config, stream_mode="checkpoints"):
                cfg = (chunk.get("config") or {}).get("configurable", {})
                ctx.checkpoint_id = cfg.get("checkpoint_id")
                emit(
                    "checkpoint.saved",
                    CheckpointSaved(
                        checkpoint_id=ctx.checkpoint_id or "",
                        step=int((chunk.get("metadata") or {}).get("step", -1)),
                        next=list(chunk.get("next") or []),
                    ),
                )
            await self._settle(mission_id)
        except asyncio.CancelledError:
            if not self._shutting_down:  # on shutdown stay "running" so recover() resumes it
                await repo.update_mission(self.db, mission_id, status="cancelled")
                emit("mission.cancelled", MissionCancelled(reason="cancelled by user"))
        except Exception as exc:
            node, err = last_failure.pop(mission_id, (None, f"{type(exc).__name__}: {exc}"))
            log.error("mission.failed", mission_id=mission_id, node=node, error=err)
            await repo.dead_letter(
                self.db,
                mission_id=mission_id,
                node=node or "?",
                error=err,
                checkpoint_id=ctx.checkpoint_id,
            )
            await repo.update_mission(self.db, mission_id, status="failed", error=err)
            emit("mission.failed", MissionFailed(error=err[:1000], node=node))
        finally:
            root.__exit__(None, None, None)
            usage = meter.usage(mission_id)
            await repo.update_mission(self.db, mission_id, tokens=usage.total)
            await bus.flush()
            mission_context.reset(token)

    async def _settle(self, mission_id: str) -> None:
        snapshot = await self.graph.aget_state(self.config(mission_id))
        if snapshot.interrupts:
            await repo.update_mission(self.db, mission_id, status="paused")
            for intr in snapshot.interrupts:
                value = dict(intr.value) if isinstance(intr.value, dict) else {"value": intr.value}
                for hook in self.interrupt_hooks:
                    await hook(mission_id, value)
            return
        values: dict[str, Any] = dict(snapshot.values or {})
        outcome = values.get("outcome") or "success"
        report = values.get("report") or {}
        report = {**report, "tokens": meter.usage(mission_id).total}
        await repo.update_mission(
            self.db, mission_id, status="completed", outcome=outcome, report=report
        )
        emit(
            "mission.completed",
            MissionCompleted(outcome=outcome, summary=str(report.get("summary", ""))[:500]),
        )
        for hook in self.completion_hooks:
            await hook(mission_id, values)

    async def resume(self, mission_id: str, decision: dict[str, Any]) -> None:
        row = await repo.get_mission(self.db, mission_id)
        if row is None or row.status != "paused":
            raise MissionNotPausedError(f"mission {mission_id} is not waiting for input")
        self.start(mission_id, Command(resume=decision), resumed=True)

    async def cancel(self, mission_id: str) -> bool:
        task = self._tasks.get(mission_id)
        if task is None or task.done():
            row = await repo.get_mission(self.db, mission_id)
            if row and row.status in {"paused", "queued"}:
                await repo.update_mission(self.db, mission_id, status="cancelled")
                return True
            return False
        task.cancel()
        await self.wait(mission_id)
        return True

    async def recover(self) -> list[str]:
        """Resume missions that were running when the process stopped."""
        resumed = []
        for row in await repo.missions_with_status(self.db, ["running", "queued"]):
            snapshot = await self.graph.aget_state(self.config(row.id))
            if snapshot.values:
                payload: Any = None  # continue from the last checkpoint
            else:  # crashed before the first checkpoint: start over
                payload = {
                    "mission_id": row.id,
                    "task": row.task,
                    "title": row.title,
                    "inputs": row.inputs,
                }
            meter.seed(row.id, row.tokens or 0)
            log.info("mission.recover", mission_id=row.id, from_checkpoint=bool(snapshot.values))
            self.start(row.id, payload, resumed=True)
            resumed.append(row.id)
        return resumed

    async def shutdown(self) -> None:
        """Stop tasks without marking missions cancelled, so recover() picks them up."""
        self._shutting_down = True
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        for task in list(self._tasks.values()):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
