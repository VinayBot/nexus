"""MCP server ``observability`` — the monitored demo-service's health, logs and metrics."""

from __future__ import annotations

from typing import Annotated, Any

import httpx
from mcp.server.mcpserver import MCPServer
from pydantic import Field

from nexus.mcp_servers.deps import McpDeps


def build(deps: McpDeps) -> MCPServer:
    mcp = MCPServer(
        "observability", instructions="Read the demo-service's health, logs and metrics."
    )

    async def fetch(path: str, **params: Any) -> Any:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(
                f"{deps.demo_url}{path}", params={k: v for k, v in params.items() if v is not None}
            )
            r.raise_for_status()
            return r.json()

    @mcp.tool(description="Current health of the demo service (status, error rate, latency).")
    async def health() -> dict[str, Any]:
        try:
            return dict(await fetch("/health"))
        except httpx.HTTPError as exc:
            return {"status": "down", "error": str(exc)}

    @mcp.tool(description="Recent structured log lines from the demo service, newest last.")
    async def read_logs(
        lines: Annotated[int, Field(ge=1, le=200)] = 40,
        level: Annotated[str | None, Field(description="ERROR, WARNING or INFO")] = None,
        contains: Annotated[str | None, Field(description="Substring filter")] = None,
    ) -> str:
        try:
            entries = await fetch("/logs", limit=lines, level=level, contains=contains)
        except httpx.HTTPError as exc:
            return f"ERROR: demo service unreachable: {exc}"
        out = []
        for e in entries:
            line = f"{e.get('ts', '')} {e.get('level', '')} {e.get('event', '')} {e.get('message', '')}"
            if e.get("traceback"):
                line += "\n" + e["traceback"][-1200:]
            out.append(line)
        return "\n".join(out) or "(no log lines)"

    @mcp.tool(description="Counters from the demo service (orders processed, errors, latency).")
    async def metrics() -> dict[str, Any]:
        try:
            return dict(await fetch("/metrics"))
        except httpx.HTTPError as exc:
            return {"error": str(exc)}

    return mcp
