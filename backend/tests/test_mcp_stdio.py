"""MCP over a real transport: a NEXUS server in its own process, spoken to over stdio.

The in-app hub uses in-process clients (fast, no ports); this proves the same
servers work for any external MCP client via JSON-RPC over stdio (Day 19).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

BACKEND = Path(__file__).resolve().parents[1]


async def test_tickets_server_over_stdio(tmp_path: Path) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "nexus.mcp_servers", "tickets"],
        cwd=str(BACKEND),
        env={**os.environ, "NEXUS_DATA_DIR": str(tmp_path / "data")},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = {t.name for t in (await session.list_tools()).tools}
        assert {"create", "get", "comment", "list_tickets"} <= tools
        created = await session.call_tool(
            "create", {"title": "Checkout is slow", "body": "Steps: open cart", "labels": ["bug"]}
        )
        ticket_id = created.content[0].text  # type: ignore[union-attr]
        assert ticket_id.startswith("T-")
        got = await session.call_tool("get", {"ticket_id": ticket_id})
        assert "Checkout is slow" in got.content[0].text  # type: ignore[union-attr]
