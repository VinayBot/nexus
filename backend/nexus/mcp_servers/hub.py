"""MCP hub: connects agents to NEXUS's six MCP servers.

Each server is a real ``MCPServer``; the hub talks to it through an MCP ``Client``
over an in-memory transport inside the backend process (full protocol: initialise,
tools/list, tools/call — no subprocess per call, and only one process ever opens
ChromaDB). ``python -m nexus.mcp_servers <name>`` serves the same servers over
stdio for external MCP clients.

The hub implements the ``ToolBox`` protocol: qualified tool names
(``server.tool``), per-agent allowlists, hidden ``workspace`` injection (the path
jail's root is always the current mission's workspace), system-only servers,
timeouts, one retry for transient failures, a call log and live health stats.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from mcp.client import Client

from nexus.agents.toolbox import ToolOutcome, run_with_events
from nexus.core.event_types import GuardrailTriggered
from nexus.core.events import emit, mission_context
from nexus.core.logging import get_logger
from nexus.core.workspace import WorkspaceManager
from nexus.db.models import ToolCallRow
from nexus.llm.types import ToolSpec
from nexus.mcp_servers import knowledge, notify, observability, sandbox_exec, tickets, workspace_fs
from nexus.mcp_servers.deps import McpDeps
from nexus.mcp_servers.sandbox_runner import SandboxRunner

log = get_logger(__name__)

BUILDERS = {
    "workspace": workspace_fs.build,
    "sandbox": sandbox_exec.build,
    "knowledge": knowledge.build,
    "tickets": tickets.build,
    "notify": notify.build,
    "observability": observability.build,
}
#: Servers agents may never call directly (policy: no email without approval).
SYSTEM_ONLY = {"notify"}
#: Parameters NEXUS fills in itself; hidden from the model's view of the schema.
HIDDEN_PARAMS = {"workspace", "mission_id"}
TIMEOUT_S = {"sandbox": 320.0}


@dataclass
class ServerStats:
    calls: int = 0
    errors: int = 0
    total_ms: float = 0.0
    last_error: str | None = None
    last_call: float | None = None
    recent: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=25))


class McpHub:
    def __init__(self, deps: McpDeps) -> None:
        self.deps = deps
        self.clients: dict[str, Client] = {}
        self.servers: dict[str, Any] = {}
        self.tools: dict[str, dict[str, Any]] = {}  # qualified name -> {server, tool, schema...}
        self.stats: dict[str, ServerStats] = {}

    async def start(self, stack: AsyncExitStack) -> None:
        for name, build in BUILDERS.items():
            server = build(self.deps)
            client = await stack.enter_async_context(Client(server))
            self.servers[name] = server
            self.clients[name] = client
            self.stats[name] = ServerStats()
            for tool in (await client.list_tools()).tools:
                self.tools[f"{name}.{tool.name}"] = {
                    "server": name,
                    "tool": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.input_schema,
                }
        log.info("mcp.hub_ready", servers=list(self.clients), tools=len(self.tools))

    # -- ToolBox protocol -----------------------------------------------------------------
    def specs(self, allowlist: list[str] | None = None) -> list[ToolSpec]:
        from nexus.agents.toolbox import allowed

        out = []
        for qname, t in self.tools.items():
            if t["server"] in SYSTEM_ONLY or not allowed(qname, allowlist):
                continue
            schema = json.loads(json.dumps(t["input_schema"]))
            props = schema.get("properties", {})
            for hidden in HIDDEN_PARAMS:
                props.pop(hidden, None)
            schema["required"] = [r for r in schema.get("required", []) if r not in HIDDEN_PARAMS]
            out.append(ToolSpec(name=qname, description=t["description"], parameters=schema))
        return out

    async def call(
        self,
        name: str,
        args: dict[str, Any],
        *,
        agent_id: str | None,
        allowlist: list[str] | None,
        workspace: str | None = None,
    ) -> ToolOutcome:
        meta = self.tools.get(name)
        if meta and meta["server"] in SYSTEM_ONLY and agent_id is not None:
            emit(
                "guardrail.triggered",
                GuardrailTriggered(
                    kind="policy",
                    detail=f"{agent_id} tried {name}: system-only (approval required)",
                    action="blocked",
                ),
            )
            return ToolOutcome(
                False, f"ERROR: {name} requires human approval and cannot be called by agents."
            )
        ctx = mission_context.get()
        mission_id = ctx.mission_id if ctx else None

        async def invoke() -> ToolOutcome:
            if meta is None:
                return ToolOutcome(
                    False, f"ERROR: unknown tool '{name}'. Known: {', '.join(sorted(self.tools))}"
                )
            call_args = dict(args)
            props = (meta["input_schema"] or {}).get("properties", {})
            if "workspace" in props:
                ws_id = workspace or call_args.get("workspace") or mission_id or "scratch"
                self.deps.workspaces.ensure(ws_id)
                call_args["workspace"] = ws_id
            if "mission_id" in props and mission_id:
                call_args.setdefault("mission_id", mission_id)
            return await self._call(meta["server"], meta["tool"], call_args)

        async def log_call(call_id: str, outcome: ToolOutcome) -> None:
            await self._log(call_id, name, args, agent_id, mission_id, outcome)

        return await run_with_events(name, args, agent_id, allowlist, invoke, on_logged=log_call)

    async def call_system(
        self, name: str, args: dict[str, Any], *, workspace: str | None = None
    ) -> ToolOutcome:
        """Trusted call from NEXUS itself (no allowlist, system-only servers allowed)."""
        return await self.call(name, args, agent_id=None, allowlist=None, workspace=workspace)

    async def _call(self, server: str, tool: str, args: dict[str, Any]) -> ToolOutcome:
        client = self.clients[server]
        last: Exception | None = None
        for attempt in (1, 2):
            try:
                async with asyncio.timeout(TIMEOUT_S.get(server, 30.0)):
                    res = await client.call_tool(tool, args)
                text = "\n".join(
                    getattr(c, "text", "") for c in res.content if getattr(c, "type", "") == "text"
                )
                data = res.structured_content
                if data is not None and not text:
                    text = json.dumps(data, default=str)[:8000]
                return ToolOutcome(
                    ok=not res.is_error and not text.startswith("ERROR"), text=text, data=data
                )
            except (TimeoutError, ConnectionError) as exc:
                last = exc
                if attempt == 1:
                    await asyncio.sleep(0.3)
        return ToolOutcome(False, f"ERROR: {server}.{tool} failed: {last!r}")

    async def _log(
        self,
        call_id: str,
        name: str,
        args: dict[str, Any],
        agent_id: str | None,
        mission_id: str | None,
        outcome: ToolOutcome,
    ) -> None:
        server = name.split(".", 1)[0]
        st = self.stats.setdefault(server, ServerStats())
        st.calls += 1
        st.total_ms += outcome.duration_ms
        st.last_call = time.time()
        if not outcome.ok:
            st.errors += 1
            st.last_error = outcome.text[:300]
        entry = {
            "id": call_id,
            "ts": st.last_call,
            "tool": name,
            "agent_id": agent_id,
            "mission_id": mission_id,
            "args": args,
            "ok": outcome.ok,
            "result": outcome.text[:1500],
            "duration_ms": outcome.duration_ms,
        }
        st.recent.appendleft(entry)
        try:
            async with self.deps.db.session() as s:
                s.add(
                    ToolCallRow(
                        id=call_id,
                        server=server,
                        tool=name.split(".", 1)[-1],
                        agent_id=agent_id,
                        mission_id=mission_id,
                        args=args,
                        ok=outcome.ok,
                        result=outcome.text[:4000],
                        duration_ms=outcome.duration_ms,
                    )
                )
        except Exception as exc:  # logging must never fail a tool call
            log.warning("mcp.log_failed", error=str(exc))

    # -- Armory -----------------------------------------------------------------------------
    async def health(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for name, client in self.clients.items():
            started = time.perf_counter()
            try:
                async with asyncio.timeout(3):
                    await client.list_tools()
                status = "ok"
            except Exception as exc:
                status = f"down: {exc!r}"[:120]
            st = self.stats.get(name, ServerStats())
            out[name] = {
                "status": status,
                "ping_ms": round((time.perf_counter() - started) * 1000, 1),
                "calls": st.calls,
                "errors": st.errors,
                "avg_ms": round(st.total_ms / st.calls, 1) if st.calls else None,
                "last_error": st.last_error,
                "last_call": st.last_call,
            }
        return out

    def describe(self) -> list[dict[str, Any]]:
        servers = []
        for name, server in self.servers.items():
            servers.append(
                {
                    "name": name,
                    "instructions": getattr(server, "instructions", "") or "",
                    "system_only": name in SYSTEM_ONLY,
                    "tools": [
                        {
                            "name": t["tool"],
                            "qualified": q,
                            "description": t["description"],
                            "input_schema": t["input_schema"],
                        }
                        for q, t in self.tools.items()
                        if t["server"] == name
                    ],
                }
            )
        return servers


@asynccontextmanager
async def start_mcp_hub(svc: Any) -> AsyncIterator[McpHub]:
    """Build deps from the service container and start every server."""
    from nexus.hitl.mailer import Mailer

    settings = svc.settings
    workspaces = WorkspaceManager(settings.workspaces_path)
    sandbox = SandboxRunner(
        prefer=settings.sandbox_backend,
        image=settings.sandbox_image,
        network=svc.policies.sandbox_network(),
    )
    mailer = Mailer(svc.db, settings.smtp_host, settings.smtp_port)
    deps = McpDeps(
        settings=settings,
        db=svc.db,
        workspaces=workspaces,
        sandbox=sandbox,
        memory=svc.extras.get("memory"),
        mailer=mailer,
    )
    svc.register("workspaces", workspaces)
    svc.register("sandbox", sandbox)
    svc.register("mailer", mailer)
    async with AsyncExitStack() as stack:
        hub = McpHub(deps)
        await hub.start(stack)
        svc.register("mcp", hub)
        yield hub
