"""Supervisor dispatch (Command + Send fan-out), worker execution, fan-in, synthesis."""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import Command, Send

from nexus.agents import reputation
from nexus.core.event_types import Handoff, SendFanin, SendFanout
from nexus.core.events import agent_context, emit
from nexus.core.services import services
from nexus.graph.nodes.common import count, limit, note, status, take
from nexus.graph.schemas import EvidenceItem, Finding, Plan, Team
from nexus.graph.subgraphs.react_worker import initial_worker_state, react_worker
from nexus.llm.types import ChatMessage
from nexus.playbooks import get_playbook
from nexus.playbooks.base import findings_text


def _owner(team: Team | None, step_id: str, fallback: str = "echo") -> str:
    if team:
        for m in team.members:
            if step_id in m.step_ids:
                return m.agent_id
    return fallback


async def dispatch(state: dict[str, Any]) -> Command[str]:
    """The Commander hands every ready step to its worker — in parallel via ``Send``."""
    p = Plan.model_validate(state["plan"])
    done = set((state.get("step_results") or {}).keys())
    ready = p.ready_steps(done)
    if not ready or count(state, "dispatch") >= limit(state, "dispatch"):
        update: dict[str, Any] = {}
        if ready:  # guard tripped with work left
            update["failure_notes"] = note(state, "dispatch round limit reached")
        return Command(goto="collect", update=update)
    status("commander", "pointing")
    team = Team.model_validate(state["team"]) if state.get("team") else None
    playbook = get_playbook(state["playbook"])
    context = findings_text(state, 1500)
    sends = []
    for step in ready:
        agent_id = _owner(team, step.id)
        spec = services().registry.get(agent_id)
        tools = playbook.default_tools(step.role) or step.tools or spec.tools
        tools = [t for t in tools if t in spec.tools] or spec.tools
        emit(
            "handoff",
            Handoff(source="commander", target=agent_id, reason=step.title),
            agent_id="commander",
        )
        sends.append(
            Send(
                "worker",
                {
                    "mission_id": state["mission_id"],
                    "playbook": state["playbook"],
                    "agent_id": agent_id,
                    "step": step.model_dump(),
                    "task": state.get("task", ""),
                    "inputs": state.get("inputs") or {},
                    "goal": p.goal,
                    "context": context,
                    "tools": tools,
                    "max_iterations": min(spec.max_steps, limit(state, "react")),
                },
            )
        )
    emit(
        "send.fanout",
        SendFanout(
            source="dispatch", target="worker", count=len(sends), items=[s.id for s in ready]
        ),
    )
    return Command(
        goto=sends,
        update={"loops": {"dispatch": 1}, "current_step": len(done)},
    )


async def worker(payload: dict[str, Any]) -> dict[str, Any]:
    """Run one plan step through the ReAct worker subgraph."""
    agent_id = payload["agent_id"]
    step = payload["step"]
    spec = services().registry.get(agent_id)
    token = agent_context.set(agent_id)
    status(agent_id, "receiving_task")
    started = time.perf_counter()
    task = (
        f"Mission: {payload['task']}\nOverall goal: {payload['goal']}\n\n"
        f"Your step ({step['id']}): {step['title']}\n{step['description']}\n"
        f"Success criteria: {step.get('success_criteria') or 'n/a'}"
    )
    try:
        custom = await get_playbook(payload["playbook"]).run_step(payload)
    except Exception as exc:
        custom = Finding(
            step_id=step["id"], agent_id=agent_id, summary=f"Step failed: {exc}"[:500], ok=False
        ).model_dump()
    if custom is not None:
        agent_context.reset(token)
        finding = Finding.model_validate(custom)
        status(agent_id, "success" if finding.ok else "failed")
        await reputation.bump(
            agent_id, steps=1, total_latency_ms=(time.perf_counter() - started) * 1000
        )
        data = finding.model_dump()
        return {"findings": [data], "step_results": {step["id"]: data}}
    try:
        out = await react_worker.ainvoke(
            initial_worker_state(
                spec,
                task,
                payload["tools"],
                context=payload.get("context", ""),
                max_iterations=payload.get("max_iterations"),
            ),
            {"recursion_limit": 60},
        )
        finding = Finding(
            step_id=step["id"],
            agent_id=agent_id,
            summary=(out.get("final") or "")[:1500],
            sources=sorted(set(out.get("sources") or [])),
            ok=bool(out.get("ok", True)) and bool(out.get("final")),
            iterations=int(out.get("iteration", 0)),
        )
        status(agent_id, "success" if finding.ok else "confused")
    except Exception as exc:  # a failed worker is a finding, not a crashed mission
        finding = Finding(
            step_id=step["id"],
            agent_id=agent_id,
            summary=f"Step failed: {type(exc).__name__}: {exc}"[:500],
            ok=False,
        )
        status(agent_id, "failed")
    finally:
        agent_context.reset(token)
    await reputation.bump(
        agent_id, steps=1, total_latency_ms=(time.perf_counter() - started) * 1000
    )
    evidence = EvidenceItem(
        kind="note", title=f"{spec.name}: {step['title']}", content=finding.summary
    ).with_hash()
    data = finding.model_dump()
    return {
        "findings": [data],
        "step_results": {step["id"]: data},
        "evidence": [evidence.model_dump()],
    }


async def collect(state: dict[str, Any]) -> dict[str, Any]:
    """Fan-in point after a round of parallel workers."""
    results = state.get("step_results") or {}
    emit("send.fanin", SendFanin(target="collect", count=len(results)))
    status("commander", "idle")
    return {"current_step": len(results)}


def after_collect(state: dict[str, Any]) -> str:
    p = Plan.model_validate(state["plan"])
    done = set((state.get("step_results") or {}).keys())
    if p.ready_steps(done) and count(state, "dispatch") < limit(state, "dispatch"):
        return take("collect", "dispatch", "more steps ready")
    if get_playbook(state["playbook"]).tournament_mode:
        return take("collect", "council", "decision matters → tournament")
    return take("collect", "synthesize", "single answer")


async def synthesize(state: dict[str, Any]) -> dict[str, Any]:
    """No tournament: the playbook's synthesis, or the Scribe merges the findings."""
    custom = await get_playbook(state["playbook"]).synthesize(state)
    if custom is not None:
        return custom
    status("quill", "thinking")
    out = await services().llm.complete(
        [
            ChatMessage.system(
                "Combine the team's findings into one clear, factual answer to the task. "
                "Do not invent facts that are not in the findings."
            ),
            ChatMessage.user(f"Task: {state['task']}\n\nFindings:\n{findings_text(state)}"),
        ],
        purpose="summarise",
        agent_id="quill",
    )
    status("quill", "idle")
    return {
        "answer": out.content,
        "messages": [AIMessage(content=out.content[:1000], name="quill")],
    }
