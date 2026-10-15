"""Policy engine: declarative safety rules loaded from YAML and enforced in code."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

BUILTIN = Path(__file__).parent / "policies.yaml"

Route = Literal["auto", "approve", "dry_run", "blocked"]
ROUTE_ORDER: dict[str, int] = {"auto": 0, "approve": 1, "dry_run": 2, "blocked": 3}


class Policy(BaseModel):
    id: str
    description: str
    kind: Literal["require_approval", "token_cap", "sandbox_network", "path_jail", "block_level"]
    applies_to: list[str] = Field(default_factory=list)
    value: Any = None
    enabled: bool = True


class PolicySet(BaseModel):
    policies: list[Policy]


class PolicyEngine:
    def __init__(self, override_path: Path | None = None) -> None:
        self.override_path = override_path
        self.reload()

    def reload(self) -> None:
        path = self.override_path if self.override_path and self.override_path.exists() else BUILTIN
        self.policies = PolicySet.model_validate(yaml.safe_load(path.read_text())).policies

    def save(self, policies: list[Policy]) -> None:
        if self.override_path is None:
            raise RuntimeError("no writable policy file configured")
        self.override_path.parent.mkdir(parents=True, exist_ok=True)
        data = PolicySet(policies=policies).model_dump()
        self.override_path.write_text(yaml.safe_dump(data, sort_keys=False))
        self.reload()

    def _enabled(self, kind: str) -> list[Policy]:
        return [p for p in self.policies if p.enabled and p.kind == kind]

    def min_route(self, action_kind: str) -> tuple[Route, list[str]]:
        """Strictest route required by approval policies for this action kind."""
        hits = [p.id for p in self._enabled("require_approval") if action_kind in p.applies_to]
        return ("approve" if hits else "auto"), hits

    def blocks_level(self, level: str) -> bool:
        return any(p.value == level for p in self._enabled("block_level"))

    def token_cap(self, default: int) -> int:
        caps = [int(p.value) for p in self._enabled("token_cap") if p.value]
        return min(caps) if caps else default

    def sandbox_network(self) -> bool:
        rules = self._enabled("sandbox_network")
        return bool(rules[0].value) if rules else False

    def path_jail(self) -> bool:
        return bool(self._enabled("path_jail"))


def stricter(a: Route, b: Route) -> Route:
    return a if ROUTE_ORDER[a] >= ROUTE_ORDER[b] else b
