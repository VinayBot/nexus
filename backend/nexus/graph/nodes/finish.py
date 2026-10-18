"""Executor → Verifier → (Rollback ⇢ replan) → Memory Writer → Reporter."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import AIMessage

from nexus.agents import reputation
from nexus.core.event_types import MemoryStored
from nexus.core.events import emit
from nexus.core.logging import get_logger
from nexus.core.services import services
from nexus.graph.nodes.common import count, limit, note, status, take
from nexus.graph.schemas import Report
from nexus.memory.long_term import MemoryUnavailableError
from nexus.playbooks import get_playbook

log = get_logger(__name__)


async def execute(state: dict[str, Any]) -> dict[str, Any]:
    status("forge", "using_tool")
    result = await get_playbook(state["playbook"]).execute(state)
    status("forge", "success" if result.ok else "failed")
    return {"execution": result.model_dump()}


def after_execute(state: dict[str, Any]) -> str:
    if (state.get("execution") or {}).get("ok"):
        return take("execute", "verify", "applied")
    return take("execute", "rollback", "execution failed")


async def verify(state: dict[str, Any]) -> dict[str, Any]:
    status("hawk", "watching")
    result = await get_playbook(state["playbook"]).verify(state)
    status("hawk", "success" if result.ok else "failed")
    return {"verification": result.model_dump()}


def after_verify(state: dict[str, Any]) -> str:
    if (state.get("verification") or {}).get("ok"):
        return take("verify", "memory_write", "healthy")
    return take("verify", "rollback", "unhealthy → rollback")


async def rollback(state: dict[str, Any]) -> dict[str, Any]:
    status("forge", "retrying")
    result = await get_playbook(state["playbook"]).rollback(state)
    reason = (state.get("verification") or {}).get("summary") or (state.get("execution") or {}).get(
        "summary", "execution failed"
    )
    return {
        "loops": {"verify": 1},
        "failure_notes": note(state, f"rolled back: {reason}"),
        "execution": {**result.model_dump(), "rolled_back": True},
        "proposals": {"__reset__": True},
        "verdict": None,
        "validation": None,
    }


def after_rollback(state: dict[str, Any]) -> str:
    if count(state, "verify") < limit(state, "verify"):
        return take("rollback", "plan", "replan after rollback")
    return take("rollback", "memory_write", "give up after rollbacks")


def _outcome(state: dict[str, Any]) -> str:
    if state.get("outcome"):
        return str(state["outcome"])
    if (state.get("execution") or {}).get("rolled_back"):
        return "rolled_back"
    if not (state.get("validation") or {}).get("ok", False):
        return "partial"
    return "success"


async def memory_write(state: dict[str, Any]) -> dict[str, Any]:
    outcome = _outcome(state)
    playbook = get_playbook(state["playbook"])
    stored: list[str] = []
    if outcome == "success":
        stored = await playbook.remember(state)
    memory = services().extras.get("memory")
    if memory is not None:
        summary = (
            f"Mission: {state.get('title')}\nPlaybook: {state['playbook']}\nOutcome: {outcome}\n"
            f"Answer: {(state.get('answer') or '')[:800]}"
        )
        try:
            doc_id = await memory.add(
                "missions",
                summary,
                {
                    "mission_id": state["mission_id"],
                    "outcome": outcome,
                    "title": state.get("title", ""),
                },
            )
            emit(
                "memory.stored",
                MemoryStored(
                    collection="missions", doc_id=doc_id, title=state.get("title", "")[:120]
                ),
            )
            stored.append(doc_id)
        except MemoryUnavailableError as exc:
            log.warning("memory.write_skipped", error=str(exc))
    team = (state.get("team") or {}).get("members", [])
    for m in team:
        await reputation.bump(m["agent_id"], missions=1)
    return {"outcome": outcome}


async def report(state: dict[str, Any]) -> dict[str, Any]:
    status("quill", "writing")
    outcome = _outcome(state)
    budget = state.get("token_budget") or {}
    verdict = state.get("verdict") or {}
    highlights = []
    if state.get("plan"):
        steps = state["plan"]["steps"]
        highlights.append(
            f"Sage planned {len(steps)} step{'s' if len(steps) != 1 else ''}: "
            + "; ".join(st["title"] for st in steps[:6])
        )
    team = [m["agent_id"].title() for m in (state.get("team") or {}).get("members", [])]
    if team:
        highlights.append(f"The Commander assigned the work to {', '.join(team)}")
    if verdict:
        highlights.append(
            f"Three solvers competed; {str(verdict.get('winner', '')).title()} won "
            f"(judge confidence {float(verdict.get('confidence') or 0):.0%})"
        )
    if (state.get("validation") or {}).get("summary"):
        highlights.append(f"Check: {state['validation']['summary']}")
    if state.get("risk"):
        route = {
            "auto": "so it ran without asking",
            "approve": "so it asked for your approval",
            "dry_run": "so it rehearsed first and asked for your approval",
            "blocked": "so policy blocked it unless you overrode it",
        }.get(state["risk"]["route"], "")
        highlights.append(f"Risk scored {state['risk']['level']}, {route}".rstrip(", "))
    if state.get("approval"):
        a = state["approval"]
        verb = {"approve": "approved", "reject": "rejected", "edit": "edited and approved"}.get(
            a["decision"], "answered"
        )
        via = "an email link" if a["channel"] == "email" else "the app"
        highlights.append(f"You {verb} it in {via}")
    if (state.get("execution") or {}).get("summary"):
        highlights.append(f"Done: {state['execution']['summary']}")
    if (state.get("verification") or {}).get("summary"):
        highlights.append(f"Verified: {state['verification']['summary']}")
    for n in dict.fromkeys(state.get("failure_notes") or []):
        highlights.append(f"Note: {n}")
    summary = {
        "success": "Mission completed successfully.",
        "rejected": "The owner rejected the proposed action; nothing was changed.",
        "blocked": "The action was blocked by policy.",
        "rolled_back": "The change was applied but failed verification and was rolled back.",
        "partial": "The team could not produce a validated result within its limits.",
    }.get(outcome, outcome)
    rep = Report(
        title=state.get("title", "Mission"),
        outcome=outcome,
        summary=summary,
        answer=state.get("answer"),
        highlights=highlights,
        tokens=int(budget.get("total_prompt", 0)) + int(budget.get("total_completion", 0)),
        duration_s=round(
            time.time() - float((state.get("inputs") or {}).get("started_at", time.time())), 1
        ),
    )
    extras = get_playbook(state["playbook"]).report_extras(state)
    status("quill", "idle")
    status("commander", "success" if outcome == "success" else "idle")
    return {
        "outcome": outcome,
        "report": {**rep.model_dump(), **extras},
        "messages": [AIMessage(content=f"Report: {summary}", name="quill")],
    }
