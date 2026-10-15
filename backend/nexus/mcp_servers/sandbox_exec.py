"""MCP server ``sandbox`` — run tests/commands on a throwaway copy of the workspace."""

from __future__ import annotations

import shlex
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from nexus.mcp_servers.deps import McpDeps

ALLOWED_COMMANDS = {"python", "pytest", "ls", "cat", "grep", "head", "tail", "wc"}


def build(deps: McpDeps) -> MCPServer:
    mcp = MCPServer(
        "sandbox", instructions="Isolated execution: no network, CPU/RAM limits, timeouts."
    )

    @mcp.tool(
        description="Run pytest on the workspace copy. Returns counts, failures and output tail."
    )
    async def run_tests(
        workspace: Annotated[str, Field(description="Workspace id (filled in by NEXUS).")],
        target: Annotated[str, Field(description="Test path or node id")] = "tests",
        timeout_s: Annotated[float, Field(ge=5, le=300)] = 90,
    ) -> dict[str, Any]:
        root = deps.workspaces.path_for(workspace)
        deps.workspaces.resolve(workspace, target.split("::")[0])  # jail check
        result = await deps.sandbox.run_tests(root, target, timeout_s=timeout_s)
        return result.as_dict()

    @mcp.tool(description=f"Run one allow-listed command ({', '.join(sorted(ALLOWED_COMMANDS))}).")
    async def run_command(
        command: Annotated[str, Field(description="Command line, e.g. 'python -c \"print(1)\"'")],
        workspace: Annotated[str, Field(description="Workspace id (filled in by NEXUS).")],
        timeout_s: Annotated[float, Field(ge=1, le=120)] = 30,
    ) -> dict[str, Any]:
        argv = shlex.split(command)
        if not argv or argv[0] not in ALLOWED_COMMANDS:
            return {"ok": False, "summary": f"command {argv[:1]} is not allowed"}
        result = await deps.sandbox.run(
            deps.workspaces.path_for(workspace), argv, timeout_s=timeout_s
        )
        return result.as_dict()

    @mcp.tool(description="Which sandbox backend is active and its isolation guarantees.")
    async def status() -> dict[str, Any]:
        return await deps.sandbox.status()

    return mcp
