"""Planner (Plan-and-Execute, also the Replanner) and Team Assembler."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from nexus.agents.registry import ROLE_ALIASES, AgentSpec
from nexus.agents.reputation import agent_stats
from nexus.core.event_types import AgentAssigned, PlanCreated
from nexus.core.events import emit
from nexus.core.services import services
from nexus.graph.nodes.common import count, status, take
from nexus.graph.schemas import ApprovalDecision, Plan, Team, TeamMember
from nexus.llm.types import ChatMessage
from nexus.playbooks import get_playbook
from nexus.playbooks.base import findings_text

WORKER_ROLES = ("researcher", "coder", "tester", "critic", "scribe", "watcher")


def _valid(plan: Plan) -> bool:
    ids = [s.id for s in plan.steps]
    if len(set(ids)) != len(ids):
        return False
    known = set(ids)
    return all(d in known and d != s.id for s in plan.steps for d in s.depends_on)


async def _ask_planner(
    playbook: Any, parts: list[str], previous: Plan | None, template: Plan
) -> Plan:
    out: Plan = await services().llm.structured(
        [
            ChatMessage.system(
                services().registry.get("sage").system_prompt
                + f"\nAllowed step roles: {', '.join(WORKER_ROLES)}.\n"
                + playbook.planner_hint
                + "\nUse short lowercase ids (e.g. 'logs', 'repro'). 1-4 steps."
            ),
            ChatMessage.user("\n\n".join(parts)),
        ],
        Plan,
        purpose="replan" if previous else "plan",
        agent_id="sage",
        default=template,
    )
    return out


async def plan(state: dict[str, Any]) -> dict[str, Any]:
    playbook = get_playbook(state["playbook"])
    previous = Plan.model_validate(state["plan"]) if state.get("plan") else None
    prepared: dict[str, Any] = {}
    if previous is None:
        prepared = await playbook.prepare(state)
        state = {**state, **prepared}
    status("sage", "thinking")
    revision = (previous.revision + 1) if previous else 0
    rewritten = state.get("rewritten") or {}
    parts = [f"Task:\n{rewritten.get('clarified_task') or state['task']}"]
    if rewritten.get("constraints"):
        parts.append("Constraints:\n- " + "\n- ".join(rewritten["constraints"]))
    if previous:
        parts.append("Previous plan:\n" + "\n".join(f"- {s.id}: {s.title}" for s in previous.steps))
        parts.append("Why it failed:\n- " + "\n- ".join(state.get("failure_notes") or ["unknown"]))
        if state.get("findings"):
            parts.append("Findings so far:\n" + findings_text(state, 1500))
    template = playbook.template_plan(state).model_copy(update={"revision": revision})
    if playbook.fixed_plan and previous is None:
        out = template
    else:
        out = await _ask_planner(playbook, parts, previous, template)
    source = out.source
    if out is template or not _valid(out):
        out, source = template, "template"
    else:
        out = out.model_copy(update={"revision": revision, "source": "llm"})
        source = "llm"
    # keep template tools on steps the model left without tools
    tmpl_tools = {s.role: s.tools for s in template.steps}
    steps = [
        s.model_copy(update={"tools": s.tools or tmpl_tools.get(s.role, [])}) for s in out.steps
    ]
    out = out.model_copy(update={"steps": steps})
    emit(
        "plan.created",
        PlanCreated(steps=[s.model_dump() for s in out.steps], revision=revision, source=source),
        agent_id="sage",
    )
    status("sage", "idle")
    update: dict[str, Any] = {
        **prepared,
        "plan": out.model_dump(mode="json"),
        "current_step": 0,
        "step_results": {"__reset__": True},
        "loops": {"dispatch": -1, "fix": -1, **({"replan": 1} if previous else {})},
        "messages": [
            AIMessage(
                content=f"Plan r{revision} ({source}): " + " → ".join(s.title for s in out.steps),
                name="sage",
            )
        ],
    }
    return update


def _reputation(agent: AgentSpec, stats: dict[str, dict[str, Any]], topic: str) -> float:
    s = stats.get(agent.id) or {}
    wins = float(s.get("wins", 0))
    topic_rep = float((s.get("topics") or {}).get(topic, 0))
    steps = max(1.0, float(s.get("steps", 0)))
    retry_rate = float(s.get("retries", 0)) / steps
    return wins * 0.5 + topic_rep - retry_rate


async def assemble(state: dict[str, Any]) -> dict[str, Any]:
    """Pick the best registry agent for each plan step (reputation-aware)."""
    status("commander", "assigning")
    p = Plan.model_validate(state["plan"])
    registry = services().registry
    stats = await agent_stats()
    members: dict[str, TeamMember] = {}
    for step in p.steps:
        role = ROLE_ALIASES.get(step.role.lower(), "researcher")
        candidates = registry.by_role(role) or registry.by_role("researcher")
        best = max(candidates, key=lambda a: _reputation(a, stats, state["playbook"]))
        m = members.setdefault(
            best.id, TeamMember(agent_id=best.id, why=f"best {role} by reputation")
        )
        m.step_ids.append(step.id)
    team = Team(members=list(members.values()))
    for m in team.members:
        emit(
            "agent.assigned",
            AgentAssigned(agent_id=m.agent_id, task=", ".join(m.step_ids)),
            agent_id=m.agent_id,
        )

    update: dict[str, Any] = {"team": team.model_dump()}
    if get_playbook(state["playbook"]).approve_team and not (state.get("team") or {}).get(
        "approved"
    ):
        raw = interrupt(
            {
                "kind": "approve_team",
                "approval_id": f"{state['mission_id']}-team-{count(state, 'approval')}",
                "summary": f"Approve a team of {len(team.members)} for: {p.goal}",
                "team": team.model_dump(),
                "plan": p.model_dump(mode="json"),
            }
        )
        decision = ApprovalDecision.model_validate(raw)
        update["approval"] = decision.model_dump()
        update["loops"] = {"approval": 1}
        if decision.decision == "edit" and decision.edited:
            if "plan" in decision.edited:
                update["plan"] = Plan.model_validate(decision.edited["plan"]).model_dump(
                    mode="json"
                )
            if "team" in decision.edited:
                team = Team.model_validate(decision.edited["team"])
        if decision.decision in {"approve", "edit"}:
            team = team.model_copy(update={"approved": True})
            update["team"] = team.model_dump()
        else:
            update["outcome"] = "rejected"
    return update


def after_assemble(state: dict[str, Any]) -> str:
    if state.get("outcome") == "rejected":
        return take("assemble", "report", "team rejected")
    return take("assemble", "dispatch", "team ready")
