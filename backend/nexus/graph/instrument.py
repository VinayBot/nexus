"""Node instrumentation: every graph node is wrapped so it emits real events.

The wrapper emits ``node.entered``/``node.exited`` (with duration and the state
keys written), ``reducer.merged`` for each update to a reducer-backed channel,
and a ``retry`` event when a node with a RetryPolicy fails and will be retried.
It also records the last failing node per mission for the dead-letter table.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.errors import GraphBubbleUp
from langgraph.types import Command

from nexus.core.event_types import NodeEntered, NodeExited, ReducerMerged, Retry
from nexus.core.events import emit, mission_context, node_context
from nexus.graph.reducers import REDUCED_CHANNELS

#: mission_id -> (node, error) of the most recent node failure
last_failure: dict[str, tuple[str, str]] = {}
_attempts: dict[tuple[str, str], int] = {}

NodeFn = Callable[[Any], Awaitable[Any]]


def _size(value: Any) -> int:
    if isinstance(value, list | dict):
        return (
            len([k for k in value if k != "__reset__"]) if isinstance(value, dict) else len(value)
        )
    return 1


def _updated_keys(result: Any) -> dict[str, Any]:
    if isinstance(result, Command):
        update = result.update
        return dict(update) if isinstance(update, dict) else {}
    return dict(result) if isinstance(result, dict) else {}


def instrument(name: str, fn: NodeFn, *, max_attempts: int = 1) -> Any:
    async def wrapped(state: Any) -> Any:
        token = node_context.set(name)
        ctx = mission_context.get()
        mission_id = ctx.mission_id if ctx else "-"
        key = (mission_id, name)
        emit("node.entered", NodeEntered(node=name), node=name)
        started = time.perf_counter()
        try:
            result = await fn(state)
        except GraphBubbleUp:  # interrupt() / parent command: not an error
            emit(
                "node.exited",
                NodeExited(
                    node=name,
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                    status="interrupted",
                ),
                node=name,
            )
            raise
        except Exception as exc:
            attempt = _attempts[key] = _attempts.get(key, 0) + 1
            last_failure[mission_id] = (name, f"{type(exc).__name__}: {exc}")
            emit(
                "node.exited",
                NodeExited(
                    node=name,
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                    status="error",
                ),
                node=name,
            )
            if attempt < max_attempts:
                emit(
                    "retry",
                    Retry(
                        layer="node",
                        key=f"node:{name}",
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        reason=str(exc)[:300],
                    ),
                    node=name,
                )
            else:
                _attempts.pop(key, None)
            raise
        finally:
            node_context.reset(token)

        _attempts.pop(key, None)
        updates = _updated_keys(result)
        current = state if isinstance(state, dict) else {}
        for channel, value in updates.items():
            reducer = REDUCED_CHANNELS.get(channel)
            if reducer is None or value is None:
                continue
            added = _size(value)
            reset = isinstance(value, dict) and value.get("__reset__")
            before = 0 if reset else _size(current.get(channel) or [])
            emit(
                "reducer.merged",
                ReducerMerged(
                    channel=channel,
                    reducer=reducer,
                    added=added,
                    total=before + added,
                    detail="reset then merged" if reset else "",
                ),
                node=name,
            )
        emit(
            "node.exited",
            NodeExited(
                node=name,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
                status="ok",
                updated=sorted(updates),
            ),
            node=name,
        )
        return result

    wrapped.__name__ = name
    wrapped.__qualname__ = name
    return wrapped
