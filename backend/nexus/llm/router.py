"""Model Router: picks the model for each call from its purpose.

Cheap, frequent work (rewrite, routing, grading, summarising, guide chat) goes to
the *fast* model; planning, solving, coding and judging go to the *main* model.
A fast-model call that fails validation twice is escalated to the main model.
Every decision is emitted as an ``llm.routed`` event.
"""

from __future__ import annotations

from typing import Literal

from nexus.core.config import ModelSet
from nexus.core.event_types import LlmRouted
from nexus.core.events import emit
from nexus.llm.types import ModelRole

FAST_PURPOSES: frozenset[str] = frozenset(
    {"rewrite", "route", "grade", "summarise", "guide", "classify", "extract", "risk_assist"}
)
MAIN_PURPOSES: frozenset[str] = frozenset(
    {"plan", "replan", "solve", "code", "judge", "review", "react", "reproduce", "debate", "team"}
)
ESCALATE_AFTER = 2


class ModelRouter:
    def __init__(self, models: ModelSet) -> None:
        self.models = models

    def role_for(self, purpose: str) -> ModelRole:
        base = purpose.split(":", 1)[0]
        if base in FAST_PURPOSES:
            return "fast"
        return "main"

    def pick(
        self,
        purpose: str,
        *,
        role: ModelRole | None = None,
        validation_failures: int = 0,
    ) -> tuple[ModelRole, str]:
        chosen: ModelRole = role or self.role_for(purpose)
        reason: str
        if chosen == "fast" and validation_failures >= ESCALATE_AFTER:
            chosen, reason = "main", f"escalated after {validation_failures} validation failures"
        elif role is not None:
            reason = "explicit role"
        else:
            reason = f"purpose '{purpose}' → {chosen}"
        model = self.models.main if chosen == "main" else self.models.fast
        r: Literal["main", "fast", "embed"] = chosen
        emit("llm.routed", LlmRouted(purpose=purpose, role=r, model=model, reason=reason))
        return chosen, model
