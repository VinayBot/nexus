"""MCP server ``demo`` — the calculator / letters / dojo-facts tools used by the
"Under the Hood" comparison, so the LangGraph agent reaches them through real MCP
while the raw-SDK agent calls the same Python functions directly."""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from nexus.llm import demo_tools
from nexus.mcp_servers.deps import McpDeps


def build(deps: McpDeps) -> MCPServer:
    mcp = MCPServer("demo", instructions="Tiny deterministic tools for agent comparisons.")

    @mcp.tool(description="Evaluate an arithmetic expression.")
    def calculator(expression: Annotated[str, Field(description="e.g. 17 * 23 + 4")]) -> str:
        try:
            return demo_tools.calculator(expression)
        except (ValueError, SyntaxError, ZeroDivisionError) as exc:
            return f"ERROR: {exc}"

    @mcp.tool(description="Count the letters in a word.")
    def count_letters(word: str) -> str:
        return demo_tools.count_letters(word)

    @mcp.tool(description="Look up a fact about the NEXUS dojo.")
    def lookup_fact(topic: str) -> str:
        return demo_tools.lookup_fact(topic)

    return mcp
