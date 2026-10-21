"""Typed payloads for every event NEXUS emits.

Each event ``type`` maps to exactly one payload model in
:data:`nexus.core.event_registry.PAYLOADS`. The bus
validates payloads on emit, and :mod:`nexus.core.export_schema` turns this module
into JSON Schema from which the frontend's TypeScript types are generated — the UI
animation layer and the backend can never disagree about an event's shape.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- mission lifecycle --------------------------------------------------------
class MissionCreated(Payload):
    title: str
    playbook: str | None
    task: str


class MissionStarted(Payload):
    resumed: bool = False


class MissionCompleted(Payload):
    outcome: Literal["success", "rejected", "blocked", "rolled_back", "partial"]
    summary: str


class MissionFailed(Payload):
    error: str
    node: str | None = None


class MissionCancelled(Payload):
    reason: str


# --- graph execution ------------------------------------------------------------
class NodeEntered(Payload):
    node: str
    step: int | None = None


class NodeExited(Payload):
    node: str
    duration_ms: float
    status: Literal["ok", "error", "interrupted"]
    updated: list[str] = Field(default_factory=list, description="State keys the node wrote.")


class EdgeTaken(Payload):
    source: str
    target: str
    label: str


class SendFanout(Payload):
    source: str
    target: str
    count: int
    items: list[str] = Field(default_factory=list)


class SendFanin(Payload):
    target: str
    count: int


class ReducerMerged(Payload):
    channel: str
    reducer: str
    added: int
    total: int
    detail: str = ""


class Handoff(Payload):
    source: str
    target: str
    reason: str


class CheckpointSaved(Payload):
    checkpoint_id: str
    step: int
    next: list[str]


class PlanCreated(Payload):
    steps: list[dict[str, Any]]
    revision: int = 0
    source: Literal["llm", "template"]


# --- agents -----------------------------------------------------------------------
class AgentAssigned(Payload):
    agent_id: str
    step_id: str | None = None
    task: str


class AgentThinking(Payload):
    agent_id: str
    text: str
    iteration: int | None = None


class AgentToken(Payload):
    agent_id: str
    text: str
    purpose: str


class AgentAction(Payload):
    agent_id: str
    tool: str
    args: dict[str, Any]
    iteration: int | None = None


class AgentObservation(Payload):
    agent_id: str
    tool: str
    summary: str
    ok: bool = True


class AgentFinal(Payload):
    agent_id: str
    answer: str


class AgentStatus(Payload):
    """Coarse robot state for the UI state machine (idle, walking, celebrating...)."""

    agent_id: str
    status: str


# --- tools ------------------------------------------------------------------------
class ToolCalled(Payload):
    server: str
    tool: str
    call_id: str
    args: dict[str, Any]
    agent_id: str | None = None


class ToolResult(Payload):
    server: str
    tool: str
    call_id: str
    ok: bool
    summary: str
    duration_ms: float


# --- council / tournament --------------------------------------------------------
class CouncilProposal(Payload):
    solver_id: str
    strategy: str
    summary: str
    label: str | None = None


class CouncilMasked(Payload):
    mapping_hidden: bool = True
    labels: list[str]


class CouncilReview(Payload):
    reviewer: str
    target_label: str
    score: float
    scores: dict[str, float]
    reason: str


class CouncilRound(Payload):
    round: int
    divergence: float
    converged: bool


class CouncilVerdict(Payload):
    winner: str
    winner_label: str
    runner_up: str | None
    confidence: float
    dissent: str
    final_scores: dict[str, float]
    escalate: bool


class SandboxTestResult(Payload):
    target: str
    passed: int
    failed: int
    errors: int
    ok: bool
    duration_ms: float
    backend: str
    summary: str = ""


# --- reliability ------------------------------------------------------------------
class Retry(Payload):
    layer: Literal["transport", "node", "validation", "fallback", "tool"]
    key: str
    attempt: int
    max_attempts: int
    reason: str
    agent_id: str | None = None


class CircuitState(Payload):
    key: str
    state: Literal["closed", "open", "half_open"]
    failures: int


class LlmRouted(Payload):
    purpose: str
    role: Literal["main", "fast", "code", "embed"]
    model: str
    reason: str


class LlmCall(Payload):
    model: str
    purpose: str
    agent_id: str | None = None
    prompt_tokens: int
    completion_tokens: int
    estimated_prompt_tokens: int
    duration_ms: float
    tokens_per_sec: float


class DeadLetter(Payload):
    node: str
    error: str
    attempts: int


# --- memory -----------------------------------------------------------------------
class MemoryPruned(Payload):
    agent_id: str
    strategy: Literal["sliding_window", "summarise"]
    before_tokens: int
    after_tokens: int
    dropped_messages: int
    budget: int


class MemorySummarised(Payload):
    agent_id: str
    before_tokens: int
    after_tokens: int
    summary: str


class MemoryStored(Payload):
    collection: str
    doc_id: str
    title: str


class MemoryRecalled(Payload):
    collection: str
    query: str
    hits: list[dict[str, Any]]


# --- safety & HITL ----------------------------------------------------------------
class RiskScored(Payload):
    level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    score: float
    factors: dict[str, float]
    route: str


class GuardrailTriggered(Payload):
    kind: Literal["injection", "pii", "policy", "allowlist", "path_jail"]
    detail: str
    action: Literal["redacted", "blocked", "flagged"]


class InterruptRaised(Payload):
    kind: Literal["approve_action", "approve_team", "edit_plan", "answer_question"]
    approval_id: str
    summary: str
    risk_level: str | None = None


class InterruptResolved(Payload):
    approval_id: str
    decision: Literal["approve", "reject", "edit", "respond"]
    by: str
    channel: Literal["ui", "email", "api", "auto"]


class EmailSent(Payload):
    to: str
    subject: str
    message_id: str
    status: Literal["sent", "outbox"]


class TimetravelFork(Payload):
    from_checkpoint: str
    new_checkpoint: str
    patch_keys: list[str]
    branch_id: str


# --- system -----------------------------------------------------------------------
class GovernorMetrics(Payload):
    ram_total_gb: float
    ram_available_gb: float
    ram_percent: float
    pressure: Literal["normal", "elevated", "critical"]
    limit: int
    configured_limit: int
    in_flight: int
    queue_depth: int
    tokens_per_sec: float
    loaded_models: list[dict[str, Any]]


class IncidentDetected(Payload):
    incident_id: str
    service: str
    signal: str
    detail: str


class ChaosToggled(Payload):
    switch: str
    enabled: bool


class ServiceHealth(Payload):
    service: str
    status: Literal["healthy", "degraded", "down"]
    error_rate: float
    latency_ms: float | None
