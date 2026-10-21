"""Dynamic Missions and saved (YAML) playbooks.

Dynamic: for tasks matching no playbook, Sage plans freely, the Commander assembles a
team from the registry, and the graph *pauses* so the human can approve or edit
the team and plan before any work starts. A successful dynamic mission can be saved
as a reusable YAML playbook (its plan becomes the template, no team approval).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from nexus.core.services import services
from nexus.graph.schemas import Plan
from nexus.playbooks.base import Playbook
from nexus.playbooks.council_qa import CouncilQA


class Dynamic(Playbook):
    id = "dynamic"
    title = "Dynamic Mission"
    description = "Anything else: the Commander composes a team from the registry; you approve the team first."
    tournament_mode = None
    approve_team = True
    planner_hint = (
        "This task matches no fixed playbook. Plan 2-4 concrete steps using the most suitable "
        "roles (researcher, coder, tester, critic, scribe). Prefer read-only investigation; the "
        "result is a written answer for the user."
    )

    async def prepare(self, state: dict[str, Any]) -> dict[str, Any]:
        """Give the team a *copy* of the demo shop's code when the task is about it.

        Without this, "review the demo-service code" ran in an empty workspace and the
        agents could only report that there were no files.
        """
        demo = services().extras.get("demo")
        if demo is not None and demo.live.is_dir() and DEMO_TOPIC.search(state.get("task", "")):
            services().workspaces.copy_from(demo.live, state["mission_id"])
        return {}

    async def validate(self, state: dict[str, Any]) -> Any:
        return await CouncilQA().validate(state)


DEMO_TOPIC = re.compile(r"demo[- ]?(service|shop)|\bthe (shop|service)\b", re.I)


class SavedPlaybookSpec(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,40}$")
    title: str
    description: str
    plan: dict[str, Any]
    tournament_mode: Literal["answer"] | None = None
    source_mission: str | None = None


class SavedPlaybook(Playbook):
    """A playbook loaded from YAML: a fixed, human-approved plan."""

    fixed_plan: ClassVar[bool] = True

    def __init__(self, spec: SavedPlaybookSpec) -> None:
        self.spec = spec
        self.id = spec.id  # type: ignore[misc]
        self.title = spec.title  # type: ignore[misc]
        self.description = spec.description  # type: ignore[misc]
        self.tournament_mode = spec.tournament_mode  # type: ignore[misc]

    def template_plan(self, state: dict[str, Any]) -> Plan:
        plan = Plan.model_validate(
            {**self.spec.plan, "goal": state.get("task", self.spec.plan.get("goal", ""))[:200]}
        )
        return plan.model_copy(update={"source": "template", "revision": 0})

    async def prepare(self, state: dict[str, Any]) -> dict[str, Any]:
        """Give the team a *copy* of the demo shop's code when the task is about it.

        Without this, "review the demo-service code" ran in an empty workspace and the
        agents could only report that there were no files.
        """
        demo = services().extras.get("demo")
        if demo is not None and demo.live.is_dir() and DEMO_TOPIC.search(state.get("task", "")):
            services().workspaces.copy_from(demo.live, state["mission_id"])
        return {}

    async def validate(self, state: dict[str, Any]) -> Any:
        return await CouncilQA().validate(state)


DEMO_TOPIC = re.compile(r"demo[- ]?(service|shop)|\bthe (shop|service)\b", re.I)


def load_saved(directory: Path) -> list[SavedPlaybook]:
    if not directory.exists():
        return []
    out = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            out.append(
                SavedPlaybook(SavedPlaybookSpec.model_validate(yaml.safe_load(path.read_text())))
            )
        except (OSError, yaml.YAMLError, ValidationError):
            continue  # a broken user file must not take the registry down
    return out


def save_playbook(directory: Path, spec: SavedPlaybookSpec) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{spec.id}.yaml"
    path.write_text(yaml.safe_dump(spec.model_dump(), sort_keys=False))
    return path
