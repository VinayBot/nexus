"""Serve one NEXUS MCP server over stdio for external MCP clients.

    uv run python -m nexus.mcp_servers workspace

Use this only while the NEXUS backend is stopped if you serve ``knowledge``: two
processes must not open the same embedded ChromaDB directory.
"""

from __future__ import annotations

import asyncio
import sys

from nexus.core.config import get_settings
from nexus.core.workspace import WorkspaceManager
from nexus.db.engine import Database
from nexus.hitl.mailer import Mailer
from nexus.mcp_servers.deps import McpDeps
from nexus.mcp_servers.hub import BUILDERS
from nexus.mcp_servers.sandbox_runner import SandboxRunner


async def _init(db: Database) -> None:
    await db.init()
    # the server runs in a new event loop: drop connections opened in this one
    await db.engine.dispose()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in BUILDERS:
        print(f"usage: python -m nexus.mcp_servers {{{'|'.join(BUILDERS)}}}", file=sys.stderr)
        raise SystemExit(2)
    name = sys.argv[1]
    settings = get_settings()
    db = Database(settings.database_target)
    asyncio.run(_init(db))
    memory = None
    if name == "knowledge":
        from nexus.core.services import build_services
        from nexus.memory.long_term import LongTermMemory

        memory = LongTermMemory(settings.chroma_path, build_services(settings).llm.embed)
    deps = McpDeps(
        settings=settings,
        db=db,
        workspaces=WorkspaceManager(settings.workspaces_path),
        sandbox=SandboxRunner(prefer=settings.sandbox_backend, image=settings.sandbox_image),
        memory=memory,
        mailer=Mailer.from_settings(db, settings),
    )
    BUILDERS[name](deps).run("stdio")


if __name__ == "__main__":
    main()
