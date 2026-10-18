"""Pydantic schemas for everything agents produce or consume.

Graph state stores these as plain dicts (``model_dump(mode="json")``) so checkpoints
stay portable JSON and a human can edit state when forking. Nodes validate on the
way in with ``Model.model_validate(state[...])``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def content_hash(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class RewrittenTask(BaseModel):
    """The Scribe's normalised version of the user's request."""

    goal: str = Field(description="One-sentence objective.")
    clarified_task: str = Field(description="The task restated clearly and completely.")
    constraints: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    is_vague: bool = Field(
        default=False, description="True only if the task cannot be attempted without asking."
    )
    question: str | None = Field(default=None, description="What to ask the user if vague.")


class RouteDecision(BaseModel):
    playbook: str = Field(description="One of the listed playbook ids.")
    reason: str


class PlanStep(BaseModel):
    id: str
    title: str
    description: str
    role: str = Field(description="Agent role best suited, e.g. researcher, coder, tester.")
    depends_on: list[str] = Field(default_factory=list)
    success_criteria: str = ""
    tools: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _slug(cls, v: str) -> str:
        return v.strip().lower().replace(" ", "-")[:40] or "step"


class Plan(BaseModel):
    goal: str
    # 8 = the Project Builder's one-step-per-file limit (MAX_FILES); LLM plans are asked for fewer
    steps: list[PlanStep] = Field(min_length=1, max_length=8)
    rationale: str = ""
    revision: int = 0
    source: Literal["llm", "template"] = "llm"

    def ready_steps(self, done: set[str]) -> list[PlanStep]:
        return [s for s in self.steps if s.id not in done and all(d in done for d in s.depends_on)]


class Finding(BaseModel):
    """What a worker learned while executing one plan step."""

    step_id: str
    agent_id: str
    summary: str
    details: str = ""
    sources: list[str] = Field(default_factory=list)
    ok: bool = True
    iterations: int = 0


class Proposal(BaseModel):
    solver_id: str
    strategy: str
    content: str = Field(description="The answer, or the patch description for code mode.")
    rationale: str = ""
    patch: dict[str, Any] | None = Field(
        default=None, description="Code mode: {'file': str, 'search': str, 'replace': str}."
    )
    round: int = 0
    tests: dict[str, Any] | None = None  # sandbox grounding results


class Review(BaseModel):
    reviewer: str
    correctness: float = Field(ge=0, le=10)
    risk: float = Field(ge=0, le=10, description="10 = very risky")
    simplicity: float = Field(ge=0, le=10)
    completeness: float = Field(ge=0, le=10)
    reason: str = ""

    @property
    def score(self) -> float:
        return round(
            (self.correctness * 0.4 + (10 - self.risk) * 0.2)
            + (self.simplicity * 0.15 + self.completeness * 0.25),
            2,
        )


class ScoreCard(BaseModel):
    proposal_id: str
    reviews: list[Review] = Field(default_factory=list)

    @property
    def mean(self) -> float:
        if not self.reviews:
            return 0.0
        return round(sum(r.score for r in self.reviews) / len(self.reviews), 2)


class Verdict(BaseModel):
    winner: str
    winner_label: str
    runner_up: str | None
    confidence: float = Field(ge=0, le=1)
    dissent: str
    final_scores: dict[str, float]
    rounds: int
    escalate: bool
    reasoning: str = ""


class EvidenceItem(BaseModel):
    kind: Literal["test_report", "diff", "log", "answer", "citation", "metric", "file", "note"]
    title: str
    content: str
    hash: str = ""

    def with_hash(self) -> EvidenceItem:
        return self.model_copy(update={"hash": self.hash or content_hash(self.kind, self.content)})


class ProposedAction(BaseModel):
    """What the Executor will do if the risk gate lets it through."""

    kind: Literal[
        "deliver_answer",
        "apply_patch",
        "comment_ticket",
        "write_project",
        "publish_page",
        "send_email",
        "run_team",
    ]
    summary: str
    target: str = ""
    files_touched: list[str] = Field(default_factory=list)
    diff_lines: int = 0
    blast_radius: Literal["none", "local", "service", "external"] = "none"
    payload: dict[str, Any] = Field(default_factory=dict)


class RiskAssessment(BaseModel):
    level: RiskLevel
    score: float
    factors: dict[str, float]
    route: Literal["auto", "approve", "dry_run", "blocked"]
    explanation: str


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject", "edit", "respond"]
    by: str = "owner"
    channel: Literal["ui", "email", "api", "auto"] = "ui"
    reason: str = ""
    edited: dict[str, Any] | None = None
    response: str | None = None


class ValidationResult(BaseModel):
    ok: bool
    summary: str
    details: str = ""
    tests: dict[str, Any] | None = None


class ExecutionResult(BaseModel):
    ok: bool
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False


class VerificationResult(BaseModel):
    ok: bool
    summary: str
    observations: list[str] = Field(default_factory=list)


class TeamMember(BaseModel):
    agent_id: str
    step_ids: list[str] = Field(default_factory=list)
    why: str = ""


class Team(BaseModel):
    members: list[TeamMember]
    approved: bool = False


class Report(BaseModel):
    title: str
    outcome: str
    summary: str
    answer: str | None = None
    highlights: list[str] = Field(default_factory=list)
    tokens: int = 0
    duration_s: float = 0.0
