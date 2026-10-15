"""Intake (guardrails) → Query Rewriter → Mission Router ⇢ Clarify (interrupt)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import interrupt

from nexus.core.services import services
from nexus.graph.nodes.common import count, limit, status, take
from nexus.graph.schemas import ApprovalDecision, RewrittenTask, RouteDecision
from nexus.graph.state import DEFAULT_LIMITS
from nexus.llm.tokens import TokenBudget
from nexus.llm.types import ChatMessage
from nexus.playbooks import all_playbooks
from nexus.safety.guardrails import scan


async def intake(state: dict[str, Any]) -> dict[str, Any]:
    """Guardrails on the raw request: redact secrets/PII, flag injection attempts."""
    status("commander", "receiving_task")
    result = scan(state.get("task", ""), source="mission task")
    settings = services().settings
    budget = TokenBudget(
        num_ctx=settings.num_ctx,
        mission_limit=services().policies.token_cap(settings.mission_token_limit),
    )
    return {
        "task": result.text,
        "title": state.get("title") or result.text.strip().splitlines()[0][:80],
        "flags": [f"injection:{p}" for p in result.injections],
        "messages": [HumanMessage(content=result.text, name="user")],
        "limits": {**DEFAULT_LIMITS, **(state.get("limits") or {})},
        "token_budget": budget.model_dump(),
        "clarifications": state.get("clarifications") or [],
        "failure_notes": [],
    }


async def rewrite(state: dict[str, Any]) -> dict[str, Any]:
    """Quill (fast model) restates the task clearly; flags it if truly ambiguous."""
    status("quill", "thinking")
    task = state["task"]
    clar = state.get("clarifications") or []
    prompt = f"Request:\n{task}"
    if clar:
        prompt += "\n\nThe user answered earlier questions:\n- " + "\n- ".join(clar)
    preset = (state.get("inputs") or {}).get("playbook")
    out = await services().llm.structured(
        [
            ChatMessage.system(
                services().registry.get("quill").system_prompt
                + "\nRestate the request as a clear task. Mark is_vague=true ONLY if it is "
                "impossible to start without asking the user something; then put that "
                "question in 'question'. Most requests are NOT vague."
            ),
            ChatMessage.user(prompt),
        ],
        RewrittenTask,
        purpose="rewrite",
        agent_id="quill",
        default=RewrittenTask(goal=task[:200], clarified_task=task),
    )
    if preset or clar:
        out = out.model_copy(update={"is_vague": False})
    status("quill", "idle")
    return {
        "rewritten": out.model_dump(),
        "messages": [AIMessage(content=f"Clarified task: {out.clarified_task}", name="quill")],
    }


async def route(state: dict[str, Any]) -> dict[str, Any]:
    """Mission Router: honour an explicit playbook, else classify with the fast model."""
    preset = (state.get("inputs") or {}).get("playbook")
    if preset and preset in {p.id for p in all_playbooks()}:
        return {"playbook": preset, "route_reason": "chosen by the user"}
    rewritten = RewrittenTask.model_validate(state["rewritten"])
    menu = "\n".join(f"- {p.id}: {p.description}" for p in all_playbooks())
    decision = await services().llm.structured(
        [
            ChatMessage.system(
                "You route engineering requests to a playbook. Options:\n"
                f"{menu}\nUse dynamic for anything that fits none of the others. Questions that "
                "only need an answer go to council_qa. Incidents or a broken service go to "
                "self_healing; requests mentioning a ticket id (T-123 or owner/repo#1) go to "
                "ticket_solver; requests to build a new small API or CLI go to project_builder."
            ),
            ChatMessage.user(rewritten.clarified_task),
        ],
        RouteDecision,
        purpose="route",
        agent_id="commander",
        default=RouteDecision(playbook="council_qa", reason="router fallback"),
    )
    available = {p.id for p in all_playbooks()}
    playbook = decision.playbook if decision.playbook in available else "council_qa"
    reason = (
        decision.reason if playbook == decision.playbook else f"{decision.playbook} unavailable"
    )
    return {
        "playbook": playbook,
        "route_reason": reason,
        "messages": [AIMessage(content=f"Routing to {playbook}: {reason}", name="commander")],
    }


def after_route(state: dict[str, Any]) -> str:
    rewritten = state.get("rewritten") or {}
    if rewritten.get("is_vague") and count(state, "clarify") < limit(state, "clarify"):
        return take("route", "clarify", "needs clarification")
    return take("route", "plan", state.get("playbook", "council_qa"))


async def clarify(state: dict[str, Any]) -> dict[str, Any]:
    """Pause and ask the human (``answer_question`` interrupt); loops back to rewrite."""
    n = count(state, "clarify")
    question = (state.get("rewritten") or {}).get("question") or "Can you clarify the request?"
    raw = interrupt(
        {
            "kind": "answer_question",
            "approval_id": f"{state['mission_id']}-clarify-{n}",
            "summary": question,
            "question": question,
        }
    )
    decision = ApprovalDecision.model_validate(raw)
    answer = decision.response or decision.reason or "(no answer)"
    return {
        "clarifications": [*(state.get("clarifications") or []), answer],
        "loops": {"clarify": 1},
        "messages": [HumanMessage(content=answer, name="user")],
    }
