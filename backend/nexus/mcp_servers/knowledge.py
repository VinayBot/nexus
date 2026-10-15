"""MCP server ``knowledge`` — semantic search over docs, Fix Library, past missions, lessons."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from nexus.mcp_servers.deps import McpDeps

Collection = Literal["all", "docs", "fix_library", "missions", "lessons"]


def build(deps: McpDeps) -> MCPServer:
    mcp = MCPServer("knowledge", instructions="RAG over NEXUS long-term memory (ChromaDB).")

    @mcp.tool(description="Semantic search. Returns the best passages with their source titles.")
    async def search(
        query: Annotated[str, Field(description="What to look for")],
        collection: Annotated[Collection, Field(description="Where to search")] = "all",
        k: Annotated[int, Field(ge=1, le=8)] = 4,
    ) -> str:
        if deps.memory is None:
            return "Knowledge base unavailable."
        cols: list[str] | None = None if collection == "all" else [str(collection)]
        hits = await deps.memory.search(query, cols, k)
        if not hits:
            return "No matching documents."
        mode = (
            "" if deps.memory.embedding_ok else " (keyword fallback: embedding model unavailable)"
        )
        lines = [f"Top {len(hits)} results{mode}:"]
        for h in hits:
            lines.append(
                f"[{h['collection']}] {h['title']} (score {h['score']}):\n{h['text'][:700]}"
            )
        return "\n\n".join(lines)

    @mcp.tool(description="How many documents each collection holds.")
    async def stats() -> dict[str, int]:
        return await deps.memory.stats() if deps.memory else {}

    return mcp
