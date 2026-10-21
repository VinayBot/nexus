"""Tables for app data (LangGraph checkpoints live in their own store).

The schema is versioned with Alembic (``nexus/db/migrations``) and upgraded on startup.
After changing a model: ``uv run alembic revision --autogenerate -m "what changed"``.
"""

from __future__ import annotations

import time
from typing import Any, ClassVar

from sqlalchemy import JSON, Float, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> float:
    return time.time()


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSON, list[Any]: JSON}


class MissionRow(Base):
    __tablename__ = "missions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    task: Mapped[str] = mapped_column(Text)
    playbook: Mapped[str | None] = mapped_column(String(40))
    #: queued | running | paused | completed | failed | cancelled
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    outcome: Mapped[str | None] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16), default="ui")
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    forked_from: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[float] = mapped_column(Float, default=now, index=True)  # newest-first lists
    updated_at: Mapped[float] = mapped_column(Float, default=now, onupdate=now)


class EventRow(Base):
    __tablename__ = "events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mission_id: Mapped[str] = mapped_column(String(32))
    seq: Mapped[int] = mapped_column(Integer)
    ts: Mapped[float] = mapped_column(Float)
    type: Mapped[str] = mapped_column(String(40))
    agent_id: Mapped[str | None] = mapped_column(String(40))
    node: Mapped[str | None] = mapped_column(String(60))
    checkpoint_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    __table_args__ = (Index("ix_events_mission_seq", "mission_id", "seq", unique=True),)


class ApprovalRow(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mission_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(24))
    #: pending | approved | rejected | edited | responded | expired
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    decision: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    risk_level: Mapped[str | None] = mapped_column(String(10))
    email_status: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[float] = mapped_column(Float, default=now)
    decided_at: Mapped[float | None] = mapped_column(Float)


class UsedTokenRow(Base):
    """Single-use bookkeeping for signed approval links."""

    __tablename__ = "used_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    used_at: Mapped[float] = mapped_column(Float, default=now)


class AuditRow(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[float] = mapped_column(Float, default=now)
    actor: Mapped[str] = mapped_column(String(80))
    channel: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(60))
    mission_id: Mapped[str | None] = mapped_column(String(32), index=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class DeadLetterRow(Base):
    __tablename__ = "dead_letters"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[str] = mapped_column(String(32), index=True)
    node: Mapped[str] = mapped_column(String(60))
    error: Mapped[str] = mapped_column(Text)
    checkpoint_id: Mapped[str | None] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class AgentStatRow(Base):
    __tablename__ = "agent_stats"
    agent_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    missions: Mapped[int] = mapped_column(Integer, default=0)
    steps: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    tournaments: Mapped[int] = mapped_column(Integer, default=0)
    tests_passed: Mapped[int] = mapped_column(Integer, default=0)
    tests_run: Mapped[int] = mapped_column(Integer, default=0)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    #: topic -> reputation points won in tournaments
    topics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ToolCallRow(Base):
    __tablename__ = "tool_calls"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts: Mapped[float] = mapped_column(Float, default=now, index=True)
    server: Mapped[str] = mapped_column(String(40), index=True)
    tool: Mapped[str] = mapped_column(String(60))
    agent_id: Mapped[str | None] = mapped_column(String(40))
    mission_id: Mapped[str | None] = mapped_column(String(32))
    args: Mapped[dict[str, Any]] = mapped_column(JSON)
    ok: Mapped[bool] = mapped_column(default=True)
    result: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)


class OutboxRow(Base):
    __tablename__ = "email_outbox"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ts: Mapped[float] = mapped_column(Float, default=now)
    to: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    html: Mapped[str] = mapped_column(Text)
    #: sent (delivered to SMTP) | outbox (SMTP unavailable; visible in the UI)
    status: Mapped[str] = mapped_column(String(16))
    mission_id: Mapped[str | None] = mapped_column(String(32))


class TicketRow(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    labels: Mapped[list[Any]] = mapped_column(JSON, default=list)
    comments: Mapped[list[Any]] = mapped_column(JSON, default=list)
    attachments: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class IncidentRow(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts: Mapped[float] = mapped_column(Float, default=now)
    service: Mapped[str] = mapped_column(String(40))
    signal: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text)
    chaos: Mapped[str | None] = mapped_column(String(40))
    mission_id: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="open")


class BranchRow(Base):
    __tablename__ = "branches"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    mission_id: Mapped[str] = mapped_column(String(32), index=True)
    label: Mapped[str] = mapped_column(String(120))
    fork_checkpoint_id: Mapped[str] = mapped_column(String(64))
    head_checkpoint_id: Mapped[str | None] = mapped_column(String(64))
    patch: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class GuideMessageRow(Base):
    __tablename__ = "guide_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(32), index=True)
    role: Mapped[str] = mapped_column(String(12))
    content: Mapped[str] = mapped_column(Text)
    actions: Mapped[list[Any]] = mapped_column(JSON, default=list)
    ts: Mapped[float] = mapped_column(Float, default=now)


class EvalRunRow(Base):
    __tablename__ = "eval_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    suite: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[float] = mapped_column(Float, default=now)
    finished_at: Mapped[float | None] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String(80))
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cases: Mapped[list[Any]] = mapped_column(JSON, default=list)


class TraceSpanRow(Base):
    __tablename__ = "trace_spans"
    span_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(32))
    mission_id: Mapped[str | None] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))
    start: Mapped[float] = mapped_column(Float)
    end: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class UserRow(Base):
    """A NEXUS account. ``role`` is owner, operator or viewer (see ``auth/policy.py``)."""

    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(64), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="viewer")
    created_at: Mapped[float] = mapped_column(Float, default=now)


class RateHitRow(Base):
    """One counted request for a rate limit; shared by every replica on the same database."""

    __tablename__ = "rate_hits"
    __table_args__ = (Index("ix_rate_hits_key_ts", "key", "ts"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(200))
    ts: Mapped[float] = mapped_column(Float)


class RevokedTokenRow(Base):
    """A signed-out session (JWT ``jti``); kept until the token would have expired anyway."""

    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[float] = mapped_column(Float, index=True)
