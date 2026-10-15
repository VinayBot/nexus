"""MCP server ``notify`` — HTML email via SMTP (Mailpit in dev).

Policy "no email without approval" is enforced by the hub: agents cannot call
this server directly; only system code (approval requests, executors running an
already-approved action) can.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from nexus.mcp_servers.deps import McpDeps


def build(deps: McpDeps) -> MCPServer:
    mcp = MCPServer("notify", instructions="Send notifications. Requires approval by policy.")

    @mcp.tool(description="Send an HTML email. Returns the message id and delivery status.")
    async def send_email(
        to: Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+$")],
        subject: Annotated[str, Field(max_length=300)],
        html: Annotated[str, Field(max_length=200_000)],
        mission_id: str | None = None,
    ) -> dict[str, Any]:
        message_id, status = await deps.mailer.send(to, subject, html, mission_id=mission_id)
        return {"message_id": message_id, "status": status}

    return mcp
