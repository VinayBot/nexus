"""Under the Hood: the same task through the raw-SDK agent and the LangGraph agent."""

from __future__ import annotations

import time
from typing import Any

from nexus.agents.registry import AgentSpec
from nexus.core.events import Event, bus
from nexus.core.services import services
from nexus.graph.subgraphs.react_worker import initial_worker_state, react_worker
from nexus.llm.demo_tools import RAW_TOOLS
from nexus.llm.raw_react_agent import RawReActAgent

LAB_AGENT = AgentSpec(
    id="lab",
    name="Lab",
    title="Comparison agent",
    role="researcher",
    persona="Careful problem solver.",
    system_prompt="You are a careful problem solver. Use tools for every calculation or lookup.",
    model_role="main",
    temperature=0.1,
    tools=["demo.*"],
    max_steps=6,
    builtin=False,
)


async def run_raw(task: str) -> dict[str, Any]:
    svc = services()
    trace: list[dict[str, Any]] = []
    agent = RawReActAgent(
        base_url=svc.settings.ollama_base_url,
        model=svc.settings.models.main,
        tools=RAW_TOOLS,
        on_event=lambda kind, data: trace.append({"kind": kind, **data}),
    )
    async with svc.governor.slot(svc.settings.models.main):
        result = await agent.run(task)
    return {
        "answer": result.answer,
        "stopped": result.stopped_reason,
        "llm_calls": result.llm_calls,
        "retries": result.retries,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "latency_ms": result.latency_ms,
        "steps": [
            {
                "thought": s.thought,
                "action": s.action,
                "input": s.action_input,
                "observation": s.observation,
                "final": s.final_answer,
            }
            for s in result.steps
        ],
        "trace": trace,
    }


async def run_graph(task: str) -> dict[str, Any]:
    svc = services()
    svc.registry.register_ephemeral(LAB_AGENT)
    captured: list[Event] = []

    def listen(e: Event) -> None:
        if e.agent_id == "lab" or (e.payload.get("agent_id") == "lab"):
            captured.append(e)

    bus.add_listener(listen)
    started = time.perf_counter()
    try:
        out = await react_worker.ainvoke(
            initial_worker_state(LAB_AGENT, task, LAB_AGENT.tools), {"recursion_limit": 40}
        )
    finally:
        bus.remove_listener(listen)
    calls = [e for e in captured if e.type == "llm.call"]
    steps = []
    for e in captured:
        if e.type == "agent.thinking":
            steps.append({"thought": e.payload["text"]})
        elif e.type == "agent.action" and steps:
            steps[-1].update(action=e.payload["tool"], input=e.payload["args"])
        elif e.type == "agent.observation" and steps:
            steps[-1]["observation"] = e.payload["summary"]
        elif e.type == "agent.final" and steps:
            steps[-1]["final"] = e.payload["answer"]
    return {
        "answer": out.get("final"),
        "stopped": "final_answer" if out.get("ok", True) and out.get("final") else "max_steps",
        "llm_calls": len(calls),
        "retries": sum(1 for e in captured if e.type == "retry"),
        "prompt_tokens": sum(int(e.payload["prompt_tokens"]) for e in calls),
        "completion_tokens": sum(int(e.payload["completion_tokens"]) for e in calls),
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "steps": steps,
        "trace": [{"kind": e.type, **e.payload} for e in captured if e.type != "agent.token"],
    }


async def compare(task: str) -> dict[str, Any]:
    raw = await run_raw(task)
    graph = await run_graph(task)
    return {"task": task, "raw": raw, "langgraph": graph}
