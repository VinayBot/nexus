"""In-process event bus: typed emit, fan-out to subscribers, batched persistence.

Nodes, agents and services call :func:`emit` synchronously; it never blocks and
never raises into business logic. The mission an event belongs to is taken from
the :data:`mission_context` context variable, which the mission runner sets
before driving the graph (asyncio copies it into every task LangGraph spawns).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, get_args

from pydantic import BaseModel, Field

from nexus.core.event_registry import EPHEMERAL, MISSION_ONLY, PAYLOADS, EventType
from nexus.core.logging import get_logger

log = get_logger(__name__)

GLOBAL = "__global__"


class Event(BaseModel):
    """Envelope shared by every event."""

    id: str
    seq: int = Field(description="Monotonic per mission (or per process for global events).")
    mission_id: str | None
    thread_id: str | None
    checkpoint_id: str | None
    ts: float = Field(description="Unix epoch seconds.")
    agent_id: str | None
    node: str | None
    type: EventType
    payload: dict[str, Any]


@dataclass
class MissionContext:
    mission_id: str
    thread_id: str
    checkpoint_id: str | None = None
    node: str | None = None


mission_context: ContextVar[MissionContext | None] = ContextVar("mission_context", default=None)
agent_context: ContextVar[str | None] = ContextVar("agent_context", default=None)
#: The graph node currently executing in this task (task-local, safe under fan-out).
node_context: ContextVar[str | None] = ContextVar("node_context", default=None)

Sink = Callable[[list[Event]], Awaitable[None]]


@dataclass(eq=False)
class Subscription:
    mission_id: str | None  # None = global channel
    queue: asyncio.Queue[Event] = field(default_factory=lambda: asyncio.Queue(maxsize=5000))
    dropped: int = 0


class EventBus:
    def __init__(self) -> None:
        self._subs: set[Subscription] = set()
        self._seq: dict[str, int] = {}
        self._sink: Sink | None = None
        self._pending: list[Event] = []
        self._flusher: asyncio.Task[None] | None = None
        self._listeners: list[Callable[[Event], None]] = []

    # -- configuration ----------------------------------------------------------
    def set_sink(self, sink: Sink | None) -> None:
        self._sink = sink

    def prime(self, mission_id: str, last_seq: int) -> None:
        """Continue numbering after ``last_seq`` (used when a mission resumes)."""
        self._seq[mission_id] = max(self._seq.get(mission_id, 0), last_seq)

    def add_listener(self, fn: Callable[[Event], None]) -> None:
        """Synchronous in-process listener (e.g. stats aggregators)."""
        self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[Event], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    # -- emit ---------------------------------------------------------------------
    def emit(
        self,
        type_: str,
        payload: BaseModel | dict[str, Any] | None = None,
        *,
        mission_id: str | None = None,
        agent_id: str | None = None,
        node: str | None = None,
    ) -> Event | None:
        model = PAYLOADS.get(type_)
        if model is None:
            log.error("event.unknown_type", type=type_)
            return None
        try:
            data = payload.model_dump() if isinstance(payload, BaseModel) else (payload or {})
            data = model.model_validate(data).model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - an emit must never break the caller
            log.error("event.invalid_payload", type=type_, error=str(exc))
            return None

        ctx = mission_context.get()
        mid = mission_id or (ctx.mission_id if ctx else None)
        key = mid or GLOBAL
        self._seq[key] = seq = self._seq.get(key, 0) + 1
        event = Event(
            id=uuid.uuid4().hex,
            seq=seq,
            mission_id=mid,
            thread_id=ctx.thread_id if ctx and ctx.mission_id == mid else mid,
            checkpoint_id=ctx.checkpoint_id if ctx and ctx.mission_id == mid else None,
            ts=time.time(),
            agent_id=agent_id or agent_context.get(),
            node=node or node_context.get(),
            type=type_,
            payload=data,
        )
        self._deliver(event)
        if mid and type_ not in EPHEMERAL and self._sink is not None:
            self._pending.append(event)
            self._ensure_flusher()
        return event

    def _deliver(self, event: Event) -> None:
        for fn in self._listeners:
            try:
                fn(event)
            except Exception as exc:  # noqa: BLE001 - one broken listener must not starve the others
                log.warning("event.listener_failed", error=str(exc))
        for sub in list(self._subs):
            if sub.mission_id is None:
                if event.type in MISSION_ONLY:
                    continue
            elif sub.mission_id != event.mission_id:
                continue
            try:
                sub.queue.put_nowait(event)
            except asyncio.QueueFull:
                sub.dropped += 1  # client resyncs from the DB using its last seq

    # -- persistence ----------------------------------------------------------------
    def _ensure_flusher(self) -> None:
        if self._flusher is None or self._flusher.done():
            # no running loop (sync caller): flush() persists later
            with contextlib.suppress(RuntimeError):
                self._flusher = asyncio.get_running_loop().create_task(self._flush_soon())

    async def _flush_soon(self) -> None:
        await asyncio.sleep(0.15)
        await self.flush()

    async def flush(self) -> None:
        if not self._pending or self._sink is None:
            return
        batch, self._pending = self._pending, []
        try:
            await self._sink(batch)
        except Exception as exc:  # noqa: BLE001 - losing a persisted batch must not stop live delivery
            log.error("event.persist_failed", count=len(batch), error=str(exc))

    # -- subscribe ----------------------------------------------------------------
    @contextlib.asynccontextmanager
    async def subscribe(self, mission_id: str | None = None) -> AsyncIterator[Subscription]:
        sub = Subscription(mission_id=mission_id)
        self._subs.add(sub)
        try:
            yield sub
        finally:
            self._subs.discard(sub)

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)

    def reset(self) -> None:
        """Test helper: forget subscribers, counters and pending events."""
        self._subs.clear()
        self._seq.clear()
        self._pending.clear()
        self._listeners.clear()
        self._sink = None


bus = EventBus()


def emit(
    type_: str,
    payload: BaseModel | dict[str, Any] | None = None,
    **kwargs: Any,
) -> Event | None:
    """Module-level shortcut for ``bus.emit``."""
    return bus.emit(type_, payload, **kwargs)


def all_event_types() -> tuple[str, ...]:
    return get_args(EventType)
