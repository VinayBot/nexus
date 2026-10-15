"""Helpers shared by main-graph nodes."""

from __future__ import annotations

from typing import Any

from nexus.core.event_types import AgentStatus, EdgeTaken
from nexus.core.events import emit
from nexus.graph.state import DEFAULT_LIMITS


def limit(state: dict[str, Any], name: str) -> int:
    return int({**DEFAULT_LIMITS, **(state.get("limits") or {})}.get(name, 3))


def count(state: dict[str, Any], name: str) -> int:
    return int((state.get("loops") or {}).get(name, 0))


def take(source: str, target: str, label: str) -> str:
    """Record which branch a conditional edge chose, then return it."""
    emit("edge.taken", EdgeTaken(source=source, target=target, label=label), node=source)
    return target


def status(agent_id: str, value: str) -> None:
    emit("agent.status", AgentStatus(agent_id=agent_id, status=value), agent_id=agent_id)


def note(state: dict[str, Any], text: str) -> list[str]:
    return [*(state.get("failure_notes") or []), text][-6:]
