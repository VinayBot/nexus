"""Typed response bodies, so OpenAPI documents real shapes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["ok", "degraded", "down"]


class Liveness(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class DependencyCheck(BaseModel):
    name: str
    status: CheckStatus
    detail: str


class Readiness(BaseModel):
    """Overall status is the worst of the individual checks."""

    status: CheckStatus
    checks: list[DependencyCheck]


class ModelRoles(BaseModel):
    main: str
    fast: str
    embed: str
    code: str | None = None
    fallback: str | None = None


class SystemInfo(BaseModel):
    version: str
    env: str
    model_profile: str
    models: ModelRoles
    num_ctx: int
    llm_max_concurrency: int
    simulation: bool = False


class EventOut(BaseModel):
    """One persisted mission event (also what the WebSocket streams)."""

    id: str
    seq: int = Field(description="Gap-free per-mission sequence number.")
    mission_id: str | None
    thread_id: str | None
    checkpoint_id: str | None
    ts: float
    agent_id: str | None
    node: str | None
    type: str
    payload: dict[str, Any]


class TokenUsage(BaseModel):
    prompt: int
    completion: int
    calls: int
    by_agent: dict[str, int]


class MissionState(BaseModel):
    values: dict[str, Any] = Field(description="The LangGraph state at the latest checkpoint.")
    next: list[str] = Field(description="Nodes that run next; empty when finished.")
    checkpoint_id: str | None
    interrupts: list[Any] = Field(description="Pending interrupt() payloads, e.g. an approval.")
    tokens: TokenUsage


class CheckpointState(BaseModel):
    summary: dict[str, Any]
    values: dict[str, Any]


class RunStatus(BaseModel):
    status: str


class AuthStatus(BaseModel):
    auth_enabled: bool
    setup_required: bool


class Me(BaseModel):
    username: str
    role: str
    auth_enabled: bool
    tokens_today: int = Field(description="Model tokens this user's missions used in 24 hours.")
    daily_token_quota: int = Field(description="0 means no cap.")
    missions_per_minute: int


class UserOut(BaseModel):
    username: str
    role: str
    created_at: float


class AuditEntry(BaseModel):
    id: int
    ts: float
    actor: str
    channel: str
    action: str
    mission_id: str | None
    detail: dict[str, Any]


class DeadLetter(BaseModel):
    id: int
    mission_id: str
    node: str
    error: str
    checkpoint_id: str | None
    created_at: float
    resolved: bool
