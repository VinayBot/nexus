"""Per-mission token meter fed by ``llm.call`` events.

The gateway asks ``check()`` before every call, which enforces the
"max tokens per mission" policy; the report and the UI read ``usage()``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from nexus.core.events import Event


class TokenCapExceededError(RuntimeError):
    pass


@dataclass
class Usage:
    prompt: int = 0
    completion: int = 0
    calls: int = 0
    by_agent: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    @property
    def total(self) -> int:
        return self.prompt + self.completion


class TokenMeter:
    def __init__(self) -> None:
        self._usage: dict[str, Usage] = defaultdict(Usage)
        self._caps: dict[str, int] = {}

    def on_event(self, event: Event) -> None:
        if event.type != "llm.call" or not event.mission_id:
            return
        u = self._usage[event.mission_id]
        u.prompt += int(event.payload.get("prompt_tokens", 0))
        u.completion += int(event.payload.get("completion_tokens", 0))
        u.calls += 1
        agent = event.payload.get("agent_id") or event.agent_id or "system"
        u.by_agent[agent] += int(event.payload.get("prompt_tokens", 0)) + int(
            event.payload.get("completion_tokens", 0)
        )

    def set_cap(self, mission_id: str, cap: int) -> None:
        self._caps[mission_id] = cap

    def seed(self, mission_id: str, total: int) -> None:
        """Restore usage after a restart (from the missions table)."""
        if mission_id not in self._usage:
            self._usage[mission_id].prompt = total

    def check(self, mission_id: str | None) -> None:
        if not mission_id or mission_id not in self._caps:
            return
        used = self._usage[mission_id].total
        if used >= self._caps[mission_id]:
            raise TokenCapExceededError(
                f"mission {mission_id} used {used} tokens (cap {self._caps[mission_id]})"
            )

    def usage(self, mission_id: str) -> Usage:
        return self._usage[mission_id]


meter = TokenMeter()
