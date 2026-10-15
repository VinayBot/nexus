"""MCP server ``workspace`` — files inside the mission workspace only (path jail)."""

from __future__ import annotations

import fnmatch
from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from nexus.mcp_servers.deps import McpDeps

MAX_READ = 20_000
WorkspaceArg = Annotated[str, Field(description="Workspace id (filled in by NEXUS).")]


def build(deps: McpDeps) -> MCPServer:
    mcp = MCPServer(
        "workspace", instructions="Read, list, search and write files in the mission workspace."
    )
    ws = deps.workspaces

    @mcp.tool(description="Read a text file from the workspace. Lines are numbered.")
    def read_file(
        path: Annotated[str, Field(description="Relative path, e.g. app/orders.py")],
        workspace: WorkspaceArg,
    ) -> str:
        p = ws.resolve(workspace, path)
        if not p.is_file():
            return f"ERROR: no such file: {path}"
        text = p.read_text(errors="replace")[:MAX_READ]
        return "\n".join(f"{i:4d}| {line}" for i, line in enumerate(text.splitlines(), 1))

    @mcp.tool(description="List files under a directory (recursive), optionally filtered by glob.")
    def list_files(
        workspace: WorkspaceArg,
        path: Annotated[str, Field(description="Relative directory")] = ".",
        pattern: Annotated[str, Field(description="Glob such as *.py")] = "*",
    ) -> str:
        base = ws.resolve(workspace, path)
        if not base.is_dir():
            return f"ERROR: not a directory: {path}"
        root = ws.path_for(workspace).resolve()
        files = sorted(
            str(f.relative_to(root))
            for f in base.rglob("*")
            if f.is_file() and fnmatch.fnmatch(f.name, pattern) and "__pycache__" not in f.parts
        )
        return "\n".join(files[:300]) or "(no files)"

    @mcp.tool(description="Search file contents for a substring; returns path:line matches.")
    def search(
        workspace: WorkspaceArg,
        query: Annotated[str, Field(description="Text to find (case-insensitive)")],
        pattern: Annotated[str, Field(description="Glob to restrict files")] = "*.py",
    ) -> str:
        root = ws.path_for(workspace).resolve()
        hits: list[str] = []
        q = query.lower()
        for f in sorted(root.rglob(pattern)):
            if not f.is_file() or "__pycache__" in f.parts:
                continue
            for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                if q in line.lower():
                    hits.append(f"{f.relative_to(root)}:{n}: {line.strip()[:160]}")
                    if len(hits) >= 60:
                        return "\n".join(hits)
        return "\n".join(hits) or f"no matches for {query!r}"

    @mcp.tool(description="Write (create or overwrite) a text file in the workspace.")
    def write_file(
        path: Annotated[str, Field(description="Relative path")],
        content: Annotated[str, Field(description="Full file content")],
        workspace: WorkspaceArg,
    ) -> str:
        p = ws.resolve(workspace, path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"wrote {len(content)} chars to {path}"

    return mcp
