"""ToolBox: how agents see and call tools, independent of where tools live.

Tools are named ``server.tool`` (``knowledge.search``, ``sandbox.run_tests``).
Every call is checked against the calling agent's allowlist, emits
``tool.called``/``tool.result`` events and is retried once on transient errors.
The production implementation (``McpToolBox`` in ``mcp_servers/hub.py``) routes
calls to MCP servers; ``LocalToolBox`` wraps plain Python callables for tests and
the Under-the-Hood comparison.
"""

from __future__ import annotations

import inspect
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from nexus.core.event_types import GuardrailTriggered, ToolCalled, ToolResult
from nexus.core.events import emit
from nexus.core.tracing import span
from nexus.llm.types import ToolSpec


@dataclass
class ToolOutcome:
    ok: bool
    text: str
    data: Any = None
    duration_ms: float = 0.0


class ToolBox(Protocol):
    def specs(self, allowlist: list[str] | None = None) -> list[ToolSpec]: ...

    async def call(
        self, name: str, args: dict[str, Any], *, agent_id: str | None, allowlist: list[str] | None
    ) -> ToolOutcome: ...


def allowed(name: str, allowlist: list[str] | None) -> bool:
    """``None`` means unrestricted (system code); ``server.*`` allows a whole server."""
    if allowlist is None:
        return True
    server = name.split(".", 1)[0]
    return name in allowlist or f"{server}.*" in allowlist


def summarise_output(text: str, limit: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


async def run_with_events(
    name: str,
    args: dict[str, Any],
    agent_id: str | None,
    allowlist: list[str] | None,
    invoke: Callable[[], Awaitable[ToolOutcome]],
    *,
    on_logged: Callable[[str, ToolOutcome], Awaitable[None]] | None = None,
) -> ToolOutcome:
    """Shared allowlist check + events + timing for every ToolBox implementation."""
    server, _, tool = name.partition(".")
    if not allowed(name, allowlist):
        emit(
            "guardrail.triggered",
            GuardrailTriggered(
                kind="allowlist", detail=f"{agent_id} may not call {name}", action="blocked"
            ),
        )
        return ToolOutcome(False, f"ERROR: tool '{name}' is not on your allowlist.")
    call_id = uuid.uuid4().hex[:12]
    emit(
        "tool.called",
        ToolCalled(server=server, tool=tool or name, call_id=call_id, args=args, agent_id=agent_id),
    )
    started = time.perf_counter()
    with span(f"tool:{name}", "tool", agent=agent_id) as s:
        try:
            outcome = await invoke()
        except Exception as exc:  # tools report errors as observations
            outcome = ToolOutcome(False, f"ERROR: {type(exc).__name__}: {exc}")
        s.set_attribute("nexus.ok", outcome.ok)
    outcome.duration_ms = round((time.perf_counter() - started) * 1000, 1)
    emit(
        "tool.result",
        ToolResult(
            server=server,
            tool=tool or name,
            call_id=call_id,
            ok=outcome.ok,
            summary=summarise_output(outcome.text),
            duration_ms=outcome.duration_ms,
        ),
    )
    if on_logged is not None:
        await on_logged(call_id, outcome)
    return outcome


class LocalToolBox:
    """Python callables exposed as tools (tests, demos)."""

    def __init__(self, tools: dict[str, tuple[ToolSpec, Callable[..., Any]]]) -> None:
        self._tools = tools

    def specs(self, allowlist: list[str] | None = None) -> list[ToolSpec]:
        return [spec for name, (spec, _) in self._tools.items() if allowed(name, allowlist)]

    async def call(
        self, name: str, args: dict[str, Any], *, agent_id: str | None, allowlist: list[str] | None
    ) -> ToolOutcome:
        async def invoke() -> ToolOutcome:
            if name not in self._tools:
                return ToolOutcome(False, f"ERROR: unknown tool '{name}'")
            _, fn = self._tools[name]
            out = fn(**args)
            if inspect.isawaitable(out):
                out = await out
            if isinstance(out, ToolOutcome):
                return out
            return ToolOutcome(True, str(out), out)

        return await run_with_events(name, args, agent_id, allowlist, invoke)
