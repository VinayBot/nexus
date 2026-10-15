"""Mission workspaces and the path jail.

Every mission that touches files gets ``<data>/workspaces/<id>/``. All file tools
resolve paths through :meth:`WorkspaceManager.resolve`, which rejects absolute
paths, ``..`` escapes and symlinks pointing outside the workspace.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from nexus.core.event_types import GuardrailTriggered
from nexus.core.events import emit

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", ".venv", ".pytest_cache", "*.pyc", ".junit.xml"
)


class PathJailError(PermissionError):
    pass


class WorkspaceManager:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, workspace_id: str) -> Path:
        if not _ID.match(workspace_id or ""):
            raise PathJailError(f"invalid workspace id {workspace_id!r}")
        return self.root / workspace_id

    def ensure(self, workspace_id: str) -> Path:
        p = self.path_for(workspace_id)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def exists(self, workspace_id: str) -> bool:
        return self.path_for(workspace_id).is_dir()

    def resolve(self, workspace_id: str, rel: str) -> Path:
        """Resolve ``rel`` inside the workspace or raise PathJailError."""
        base = self.path_for(workspace_id).resolve()
        rel = (rel or ".").strip()
        if Path(rel).is_absolute() or rel.startswith("~"):
            self._deny(workspace_id, rel, "absolute path")
        target = (base / rel).resolve()
        if target != base and base not in target.parents:
            self._deny(workspace_id, rel, "escapes the workspace")
        return target

    def _deny(self, workspace_id: str, rel: str, why: str) -> None:
        emit(
            "guardrail.triggered",
            GuardrailTriggered(
                kind="path_jail", detail=f"{rel!r} {why} ({workspace_id})", action="blocked"
            ),
        )
        raise PathJailError(f"path {rel!r} {why}")

    def copy_from(self, src: Path, workspace_id: str) -> Path:
        dest = self.path_for(workspace_id)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, ignore=IGNORE)
        return dest
