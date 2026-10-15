"""Playbook interface: how a mission type plugs into the one shared main graph.

The main graph owns orchestration (routing, planning, delegation, tournaments,
validation, risk gate, approval, execution, verification, memory, report). A
playbook supplies the domain pieces through these hooks. Defaults describe a
read-only mission whose result is an answer.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel

from nexus.graph.schemas import (
    ExecutionResult,
    Plan,
    PlanStep,
    ProposedAction,
    ValidationResult,
    VerificationResult,
)


class TournamentBrief(BaseModel):
    """What the Council needs from the playbook to run a tournament."""

    mode: Literal["answer", "code"]
    topic: str
    question: str
    context: str = ""
    code_context: dict[str, Any] | None = None
    solvers: list[str] = ["ronin_a", "ronin_b", "ronin_c"]
    critic: str | None = "kiri"
    max_rounds: int = 1
    #: Proposals that enter the tournament without an LLM call (e.g. a Fix Library patch).
    seed_proposals: dict[str, dict[str, Any]] = {}


class Playbook:
    id: ClassVar[str]
    title: ClassVar[str]
    description: ClassVar[str]
    #: None → no tournament; the best worker finding is synthesised into the answer.
    tournament_mode: ClassVar[Literal["answer", "code"] | None] = "answer"
    #: Guidance appended to the planner prompt.
    planner_hint: ClassVar[str] = ""
    #: Team approval interrupt before work starts (Dynamic Missions).
    approve_team: ClassVar[bool] = False
    #: Use ``template_plan`` as-is instead of asking the planner (spec-driven plans).
    fixed_plan: ClassVar[bool] = False

    # -- preparation --------------------------------------------------------------
    async def prepare(self, state: dict[str, Any]) -> dict[str, Any]:
        """Deterministic setup before the first plan (workspace, reproduction…).

        Returns state updates; ``inputs`` replaces the mission inputs.
        """
        return {}

    async def run_step(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Custom executor for a plan step; return a Finding dict, or None for ReAct."""
        return None

    async def synthesize(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """Custom synthesis (no-tournament playbooks); None → the Scribe's summary."""
        return None

    # -- planning -----------------------------------------------------------------
    def template_plan(self, state: dict[str, Any]) -> Plan:
        """Fallback plan used when the planner's output is unusable."""
        task = state.get("task", "")
        return Plan(
            goal=task[:200],
            source="template",
            steps=[
                PlanStep(
                    id="research",
                    title="Gather relevant facts",
                    description=f"Search the knowledge base for facts relevant to: {task}",
                    role="researcher",
                    success_criteria="Relevant facts found and cited, or none exist.",
                )
            ],
        )

    def default_tools(self, role: str) -> list[str] | None:
        """Override the agent's allowlist for a role in this playbook (None = keep)."""
        return None

    # -- deciding ------------------------------------------------------------------
    def tournament_brief(self, state: dict[str, Any]) -> TournamentBrief:
        return TournamentBrief(
            mode=self.tournament_mode or "answer",
            topic=self.id,
            question=state.get("task", ""),
            context=findings_text(state),
        )

    async def ground(self, proposal: dict[str, Any], tstate: dict[str, Any]) -> dict[str, Any]:
        """Code mode: run a proposal's patch in a sandbox. Returns test results."""
        return {}

    async def validate(self, state: dict[str, Any]) -> ValidationResult:
        return ValidationResult(ok=bool(state.get("answer")), summary="Answer produced.")

    # -- acting --------------------------------------------------------------------
    def proposed_action(self, state: dict[str, Any]) -> ProposedAction:
        return ProposedAction(kind="deliver_answer", summary="Deliver the answer to the user.")

    async def dry_run(self, state: dict[str, Any]) -> ExecutionResult:
        return ExecutionResult(ok=True, summary="Nothing to rehearse.", dry_run=True)

    async def execute(self, state: dict[str, Any]) -> ExecutionResult:
        return ExecutionResult(ok=True, summary="Answer delivered.")

    async def verify(self, state: dict[str, Any]) -> VerificationResult:
        return VerificationResult(ok=True, summary="Nothing external to verify.")

    async def rollback(self, state: dict[str, Any]) -> ExecutionResult:
        return ExecutionResult(ok=True, summary="Nothing to roll back.")

    async def remember(self, state: dict[str, Any]) -> list[str]:
        """Write long-term memories; returns ids stored."""
        return []

    def report_extras(self, state: dict[str, Any]) -> dict[str, Any]:
        return {}


def findings_text(state: dict[str, Any], limit: int = 3500) -> str:
    lines = []
    for f in state.get("findings", []):
        mark = "✓" if f.get("ok", True) else "?"
        lines.append(f"{mark} [{f.get('agent_id')} · {f.get('step_id')}] {f.get('summary', '')}")
    text = "\n".join(lines)
    return text[:limit]
