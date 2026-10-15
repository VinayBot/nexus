"""Dependencies shared by NEXUS's own MCP servers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nexus.core.config import Settings
from nexus.core.workspace import WorkspaceManager
from nexus.db.engine import Database
from nexus.mcp_servers.sandbox_runner import SandboxRunner

if TYPE_CHECKING:
    from nexus.hitl.mailer import Mailer
    from nexus.memory.long_term import LongTermMemory


@dataclass
class McpDeps:
    settings: Settings
    db: Database
    workspaces: WorkspaceManager
    sandbox: SandboxRunner
    memory: LongTermMemory | None
    mailer: Mailer

    @property
    def demo_url(self) -> str:
        return f"http://127.0.0.1:{self.settings.demo_service_port}"
