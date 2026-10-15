"""Agent Registry: robot specs loaded from YAML, editable from the UI.

Built-in specs live in ``agents/specs/*.yaml``; UI edits and new agents are
written to ``<data_dir>/agents/*.yaml`` and override built-ins with the same id.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

SPECS_DIR = Path(__file__).parent / "specs"


class Avatar(BaseModel):
    color: str = Field(
        default="#E8ECF2", description="Shell tone (light ceramic or dark gunmetal)."
    )
    accent: str = Field(
        default="#4FE3F0", description="Role colour for lights, stripes and visor glow."
    )
    prop: str = "none"
    size: Literal["small", "normal", "large"] = "normal"


class AgentSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    title: str
    role: str
    persona: str
    system_prompt: str
    model_role: Literal["main", "fast"] = "main"
    temperature: float = Field(default=0.2, ge=0, le=1.5)
    tools: list[str] = Field(default_factory=list, description="MCP tool allowlist.")
    max_steps: int = Field(default=5, ge=1, le=12)
    num_ctx: int = Field(default=4096, ge=1024)
    strategy: str | None = None
    avatar: Avatar = Field(default_factory=Avatar)
    risk_level: Literal["low", "medium", "high"] = "low"
    builtin: bool = True


class AgentRegistry:
    def __init__(self, override_dir: Path | None = None) -> None:
        self.override_dir = override_dir
        self._agents: dict[str, AgentSpec] = {}
        self.reload()

    def reload(self) -> None:
        agents: dict[str, AgentSpec] = {}
        for path in sorted(SPECS_DIR.glob("*.yaml")):
            spec = AgentSpec.model_validate(yaml.safe_load(path.read_text()))
            agents[spec.id] = spec
        if self.override_dir and self.override_dir.exists():
            for path in sorted(self.override_dir.glob("*.yaml")):
                data = yaml.safe_load(path.read_text())
                spec = AgentSpec.model_validate({**data, "builtin": data.get("id") in agents})
                agents[spec.id] = spec
        self._agents = agents

    def register_ephemeral(self, spec: AgentSpec) -> None:
        """An in-memory agent (e.g. the Under-the-Hood lab agent); not persisted."""
        self._agents.setdefault(spec.id, spec)

    def get(self, agent_id: str) -> AgentSpec:
        if agent_id not in self._agents:
            raise KeyError(f"unknown agent '{agent_id}'")
        return self._agents[agent_id]

    def all(self) -> list[AgentSpec]:
        return list(self._agents.values())

    def by_role(self, role: str) -> list[AgentSpec]:
        role = role.lower()
        return [a for a in self._agents.values() if a.role == role]

    def save(self, spec: AgentSpec) -> AgentSpec:
        if self.override_dir is None:
            raise RuntimeError("registry has no writable directory")
        self.override_dir.mkdir(parents=True, exist_ok=True)
        data = spec.model_dump(exclude={"builtin"})
        (self.override_dir / f"{spec.id}.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
        self.reload()
        return self.get(spec.id)

    def delete(self, agent_id: str) -> None:
        if self.override_dir is None:
            return
        path = self.override_dir / f"{agent_id}.yaml"
        if path.exists():
            path.unlink()
        self.reload()


#: Plan-step roles → registry roles, used by the Team Assembler.
ROLE_ALIASES: dict[str, str] = {
    "researcher": "researcher",
    "research": "researcher",
    "scout": "researcher",
    "analyst": "researcher",
    "investigator": "researcher",
    "context": "researcher",
    "coder": "coder",
    "developer": "coder",
    "engineer": "coder",
    "implementer": "coder",
    "tester": "tester",
    "validator": "tester",
    "qa": "tester",
    "reviewer": "critic",
    "critic": "critic",
    "writer": "scribe",
    "scribe": "scribe",
    "summariser": "scribe",
    "planner": "planner",
    "watcher": "watcher",
    "monitor": "watcher",
    "messenger": "messenger",
    "notifier": "messenger",
}
