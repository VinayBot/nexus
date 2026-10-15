"""Risk Gate → (dry-run) → human approval interrupt."""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from nexus.core.event_types import RiskScored
from nexus.core.events import emit
from nexus.core.services import services
from nexus.graph.nodes.common import count, note, status, take
from nexus.graph.schemas import ApprovalDecision, ProposedAction, RiskAssessment
from nexus.hitl.history import approval_history
from nexus.playbooks import get_playbook
from nexus.safety.risk import score_risk


async def risk_gate(state: dict[str, Any]) -> dict[str, Any]:
    playbook = get_playbook(state["playbook"])
    action = playbook.proposed_action(state)
    winner_tests = None
    verdict = state.get("verdict")
    if verdict and state.get("proposals"):
        winner_tests = (state["proposals"].get(verdict["winner"]) or {}).get("tests")
    history = await approval_history(action.kind)
    risk = score_risk(
        action,
        tests=winner_tests or (state.get("validation") or {}).get("tests"),
        verdict=verdict,
        history=history,
        policies=services().policies,
    )
    emit(
        "risk.scored",
        RiskScored(level=risk.level, score=risk.score, factors=risk.factors, route=risk.route),
    )
    return {"action": action.model_dump(), "risk": risk.model_dump()}


def after_gate(state: dict[str, Any]) -> str:
    risk = RiskAssessment.model_validate(state["risk"])
    target = {
        "auto": "execute",
        "approve": "approval",
        "dry_run": "dry_run",
        "blocked": "approval",
    }[risk.route]
    return take("risk_gate", target, f"{risk.level} → {risk.route}")


async def dry_run(state: dict[str, Any]) -> dict[str, Any]:
    status("mamoru", "testing")
    result = await get_playbook(state["playbook"]).dry_run(state)
    status("mamoru", "success" if result.ok else "failed")
    return {"execution": result.model_dump()}


async def approval(state: dict[str, Any]) -> dict[str, Any]:
    """Pause the graph until a human approves, rejects, edits or responds."""
    action = ProposedAction.model_validate(state["action"])
    risk = RiskAssessment.model_validate(state["risk"])
    for agent in ("shogun", "hikyaku"):
        status(agent, "waiting_approval")
    raw = interrupt(
        {
            "kind": "approve_action",
            "approval_id": f"{state['mission_id']}-action-{count(state, 'approval')}",
            "summary": action.summary,
            "action": action.model_dump(),
            "risk": risk.model_dump(),
            "requires_override": risk.route == "blocked",
            "verdict": state.get("verdict"),
            "dry_run": state.get("execution")
            if (state.get("execution") or {}).get("dry_run")
            else None,
            "evidence": _approval_evidence(state),
            "answer": (state.get("answer") or "")[:2000],
        }
    )
    decision = ApprovalDecision.model_validate(raw)
    update: dict[str, Any] = {"approval": decision.model_dump(), "loops": {"approval": 1}}
    if decision.decision == "edit" and decision.edited:
        merged = {**action.model_dump(), **decision.edited}
        update["action"] = ProposedAction.model_validate(merged).model_dump()
    elif decision.decision == "reject":
        update["outcome"] = "rejected"
    elif decision.decision == "respond":
        update["failure_notes"] = note(state, f"owner said: {decision.response or decision.reason}")
    for agent in ("shogun", "hikyaku"):
        status(agent, "idle")
    return update


def _approval_evidence(state: dict[str, Any]) -> list[dict[str, str]]:
    """The final winner's diff and tests first, then the latest supporting notes."""
    items: list[dict[str, str]] = []
    verdict = state.get("verdict") or {}
    winner = (state.get("proposals") or {}).get(verdict.get("winner", "")) or {}
    tests = winner.get("tests") or {}
    if tests.get("diff"):
        items.append(
            {
                "kind": "diff",
                "title": f"Final patch ({winner.get('strategy')})",
                "content": tests["diff"][:2500],
            }
        )
    if tests:
        body = f"{tests.get('summary', '')}\n" + "\n".join(tests.get("failures") or [])
        items.append(
            {
                "kind": "test_report",
                "title": "Sandbox tests of the final patch",
                "content": body[:1500],
            }
        )
    seen = {"diff", "test_report"} if tests else set()
    for e in reversed(state.get("evidence") or []):
        if e["kind"] in seen or len(items) >= 5:
            continue
        items.append({"kind": e["kind"], "title": e["title"], "content": e["content"][:1500]})
    return items


def after_approval(state: dict[str, Any]) -> str:
    decision = (state.get("approval") or {}).get("decision")
    if decision in {"approve", "edit"}:
        return take("approval", "execute", decision)
    if decision == "respond":
        return take("approval", "plan", "owner feedback → replan")
    return take("approval", "memory_write", "rejected")
