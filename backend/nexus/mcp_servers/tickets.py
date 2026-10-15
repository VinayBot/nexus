"""MCP server ``tickets`` — local mock ticket system (default) + optional GitHub Issues.

A ticket id like ``T-1`` is local. ``owner/repo#123`` uses GitHub when
``NEXUS_GITHUB_TOKEN`` is set (read issue, comment); attachments are kept locally
and linked in the comment because the Issues API has no attachment endpoint.
"""

from __future__ import annotations

import re
import time
from typing import Annotated, Any

import httpx
from mcp.server.mcpserver import MCPServer
from pydantic import Field
from sqlalchemy import select

from nexus.db.models import TicketRow
from nexus.mcp_servers.deps import McpDeps

GH = re.compile(r"^(?P<repo>[\w.-]+/[\w.-]+)#(?P<num>\d+)$")
TicketId = Annotated[str, Field(description="Local id like T-1, or owner/repo#123 for GitHub")]


def _row(t: TicketRow) -> dict[str, Any]:
    return {
        "id": t.id,
        "title": t.title,
        "body": t.body,
        "status": t.status,
        "labels": t.labels,
        "comments": t.comments,
        "attachments": [
            {"name": a["name"], "size": len(a.get("content", ""))} for a in t.attachments
        ],
        "source": "local",
    }


def build(deps: McpDeps) -> MCPServer:
    mcp = MCPServer("tickets", instructions="Read tickets, comment on them and attach evidence.")
    token = deps.settings.github_token

    async def gh(method: str, path: str, **kw: Any) -> Any:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.request(
                method,
                f"https://api.github.com{path}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                **kw,
            )
            r.raise_for_status()
            return r.json()

    @mcp.tool(description="List tickets in the local tracker.")
    async def list_tickets(
        status: Annotated[str, Field(description="open | closed | all")] = "open",
    ) -> list[dict[str, Any]]:
        async with deps.db.session() as s:
            q = select(TicketRow).order_by(TicketRow.created_at.desc())
            if status != "all":
                q = q.where(TicketRow.status == status)
            return [
                {"id": t.id, "title": t.title, "status": t.status, "labels": t.labels}
                for t in (await s.execute(q)).scalars()
            ]

    @mcp.tool(description="Get one ticket with its body and comments.")
    async def get(ticket_id: TicketId) -> dict[str, Any]:
        m = GH.match(ticket_id)
        if m:
            if not token:
                return {"error": "GitHub token not configured (NEXUS_GITHUB_TOKEN)"}
            issue = await gh("GET", f"/repos/{m['repo']}/issues/{m['num']}")
            return {
                "id": ticket_id,
                "title": issue["title"],
                "body": issue.get("body") or "",
                "status": issue["state"],
                "labels": [lab["name"] for lab in issue.get("labels", [])],
                "comments": [],
                "source": "github",
            }
        async with deps.db.session() as s:
            t = await s.get(TicketRow, ticket_id)
            return _row(t) if t else {"error": f"no ticket {ticket_id}"}

    @mcp.tool(description="Add a comment to a ticket.")
    async def comment(ticket_id: TicketId, body: Annotated[str, Field(max_length=20_000)]) -> str:
        m = GH.match(ticket_id)
        if m:
            if not token:
                return "ERROR: GitHub token not configured"
            res = await gh(
                "POST", f"/repos/{m['repo']}/issues/{m['num']}/comments", json={"body": body}
            )
            return f"commented: {res.get('html_url')}"
        async with deps.db.session() as s:
            t = await s.get(TicketRow, ticket_id)
            if t is None:
                return f"ERROR: no ticket {ticket_id}"
            t.comments = [*t.comments, {"author": "nexus", "body": body, "ts": time.time()}]
        return f"commented on {ticket_id}"

    @mcp.tool(description="Attach an evidence file (text) to a local ticket.")
    async def attach(
        ticket_id: TicketId,
        name: Annotated[str, Field(pattern=r"^[\w.\-]{1,80}$")],
        content: Annotated[str, Field(max_length=200_000)],
    ) -> str:
        async with deps.db.session() as s:
            t = await s.get(TicketRow, ticket_id)
            if t is None:
                return f"ERROR: no local ticket {ticket_id}"
            t.attachments = [
                *[a for a in t.attachments if a["name"] != name],
                {"name": name, "content": content, "ts": time.time()},
            ]
        return f"attached {name} ({len(content)} chars) to {ticket_id}"

    @mcp.tool(description="Set a local ticket's status (open/closed).")
    async def set_status(
        ticket_id: TicketId, status: Annotated[str, Field(pattern="^(open|closed)$")]
    ) -> str:
        async with deps.db.session() as s:
            t = await s.get(TicketRow, ticket_id)
            if t is None:
                return f"ERROR: no local ticket {ticket_id}"
            t.status = status
        return f"{ticket_id} is now {status}"

    return mcp
