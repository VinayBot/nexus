"""``MissionState`` — the typed state every node of the main graph reads and updates.

Channels with an ``Annotated[..., reducer]`` type merge concurrent updates (see
``graph/reducers.py``); plain channels are last-write-wins. Values are JSON-safe
dicts mirroring the schemas in ``graph/schemas.py``.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from nexus.graph.reducers import append_list, dedupe_append, merge_dict, merge_scores, sum_counts

#: Upper bounds for every cycle in the graph. Stored in state (``limits``) so a
#: fork can raise or lower them; these are the defaults.
DEFAULT_LIMITS: dict[str, int] = {
    "clarify": 2,  # clarify → rewrite loop
    "dispatch": 8,  # supervisor ⇄ workers rounds
    "fix": 2,  # validate → tournament (test → fix → test)
    "replan": 2,  # validate/verify failures → planner
    "verify": 2,  # verify → rollback → replan
    "debate": 2,  # council debate rounds
    "react": 6,  # per-worker ReAct iterations
}


class MissionState(TypedDict, total=False):
    # identity & input
    mission_id: str
    title: str
    task: str  # redacted user task
    playbook: str  # council_qa | self_healing | ticket_solver | project_builder | dynamic
    inputs: dict[str, Any]  # playbook-specific inputs (ticket id, incident, docs…)
    flags: list[str]  # guardrail flags raised on intake

    # conversation log of the supervisor (LangChain messages, add_messages reducer)
    messages: Annotated[list[AnyMessage], add_messages]

    # understanding & planning
    rewritten: dict[str, Any] | None  # RewrittenTask
    route_reason: str
    clarifications: list[str]
    plan: dict[str, Any] | None  # Plan
    current_step: int
    team: dict[str, Any] | None  # Team

    # parallel work (reducers)
    findings: Annotated[list[dict[str, Any]], append_list]  # Finding
    step_results: Annotated[dict[str, Any], merge_dict]  # step_id -> Finding
    proposals: Annotated[dict[str, Any], merge_dict]  # solver_id -> Proposal
    scores: Annotated[dict[str, Any], merge_scores]  # proposal_id -> ScoreCard
    evidence: Annotated[list[dict[str, Any]], dedupe_append]  # EvidenceItem

    # decision
    verdict: dict[str, Any] | None  # Verdict
    answer: str | None
    validation: dict[str, Any] | None  # ValidationResult
    action: dict[str, Any] | None  # ProposedAction
    risk: dict[str, Any] | None  # RiskAssessment
    approval: dict[str, Any] | None  # ApprovalDecision
    execution: dict[str, Any] | None  # ExecutionResult
    verification: dict[str, Any] | None  # VerificationResult

    # control
    retry_counts: Annotated[dict[str, int], sum_counts]
    loops: Annotated[dict[str, int], sum_counts]
    limits: dict[str, int]
    token_budget: dict[str, Any]  # TokenBudget
    summary: str  # rolling summary used by summarisation pruning
    outcome: str | None
    report: dict[str, Any] | None
    failure_notes: list[str]
