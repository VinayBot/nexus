"""ReAct worker subgraph: Thought → Action → Observation → … → Final.

``think`` asks the agent's model for ONE structured turn (schema-constrained JSON:
thought + action + action_input, or thought + final_answer). ``act`` runs the tool
through the ToolBox and appends the fenced observation. The two nodes form a cycle
guarded by ``max_iterations``; when the guard trips, ``finalize`` forces an answer
from what was gathered so far.

Schema-constrained turns (Ollama ``format=<json schema>``) are far more reliable
than native tool calling on 3–8B local models, and every Thought is real model
output streamed to the UI.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field, create_model

from nexus.agents.registry import AgentSpec
from nexus.core.event_types import AgentAction, AgentFinal, AgentObservation, AgentThinking
from nexus.core.events import emit
from nexus.core.services import services
from nexus.llm.types import ChatMessage, ToolSpec
from nexus.memory.pruning import prune
from nexus.safety.guardrails import UNTRUSTED_RULE, fence

FINAL = "final"


class WorkerState(TypedDict, total=False):
    agent_id: str
    task: str  # the step's instructions, incl. mission context
    messages: list[dict[str, Any]]  # ChatMessage dumps
    tools: list[str]
    iteration: int
    max_iterations: int
    final: str | None
    sources: list[str]
    summary: str
    ok: bool


def _turn_schema(tool_names: list[str]) -> type[BaseModel]:
    actions = (*tool_names, FINAL)
    return create_model(
        "ReActTurn",
        thought=(str, Field(description="Brief reasoning for this step.")),
        action=(Literal[actions], Field(description=f"A tool name, or '{FINAL}' when done.")),  # type: ignore[arg-type]
        action_input=(dict[str, Any], Field(default_factory=dict)),
        final_answer=(
            str | None,
            Field(default=None, description=f"Required when action is '{FINAL}'."),
        ),
    )


def _describe(specs: list[ToolSpec]) -> str:
    if not specs:
        return "(no tools — answer from the task context)"
    lines = []
    for s in specs:
        props = s.parameters.get("properties", {})
        args = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in props.items())
        lines.append(f"- {s.name}({args}): {s.description}")
    return "\n".join(lines)


def system_prompt(spec: AgentSpec, tools: list[ToolSpec]) -> str:
    return (
        f"{spec.system_prompt.strip()}\n\n"
        f"You work in ReAct style. Available tools:\n{_describe(tools)}\n\n"
        "Each turn, reply with JSON: a short 'thought', then either an 'action' (a tool "
        f"name) with 'action_input', or action '{FINAL}' with your 'final_answer'. "
        "Use tools to look things up instead of guessing. Keep final answers factual "
        "and concise, and say which sources you used.\n\n" + UNTRUSTED_RULE
    )


def _messages(state: WorkerState) -> list[ChatMessage]:
    return [ChatMessage.model_validate(m) for m in state.get("messages", [])]


async def think(state: WorkerState) -> dict[str, Any]:
    svc = services()
    spec: AgentSpec = svc.registry.get(state["agent_id"])
    messages = _messages(state)
    budget = spec.num_ctx - 768  # room for the reply
    pruned = await prune(
        messages,
        budget,
        agent_id=spec.id,
        strategy=svc.settings.pruning_strategy,
        summariser=summariser_for(spec.id),
        previous_summary=state.get("summary", ""),
    )
    tool_names = [s.name for s in svc.toolbox.specs(state.get("tools", []))]
    turn = await svc.llm.structured(
        pruned.messages,
        _turn_schema(tool_names),
        purpose="react",
        role=spec.model_role,
        agent_id=spec.id,
        temperature=spec.temperature,
    )
    data = turn.model_dump()
    iteration = state.get("iteration", 0) + 1
    emit(
        "agent.thinking", AgentThinking(agent_id=spec.id, text=data["thought"], iteration=iteration)
    )
    msgs = [m.model_dump() for m in pruned.messages]
    msgs.append(ChatMessage.assistant(turn.model_dump_json()).model_dump())
    update: dict[str, Any] = {"messages": msgs, "iteration": iteration}
    if pruned.summary:
        update["summary"] = pruned.summary
    if data["action"] == FINAL:
        answer = (data.get("final_answer") or data["thought"]).strip()
        emit("agent.final", AgentFinal(agent_id=spec.id, answer=answer[:2000]))
        update["final"] = answer
    return update


async def act(state: WorkerState) -> dict[str, Any]:
    svc = services()
    spec: AgentSpec = svc.registry.get(state["agent_id"])
    last = ChatMessage.model_validate(state["messages"][-1])
    from nexus.reliability.json_repair import extract_json

    turn = extract_json(last.content)
    tool, args = str(turn.get("action")), dict(turn.get("action_input") or {})
    emit(
        "agent.action",
        AgentAction(agent_id=spec.id, tool=tool, args=args, iteration=state.get("iteration")),
    )
    outcome = await svc.toolbox.call(tool, args, agent_id=spec.id, allowlist=state.get("tools", []))
    emit(
        "agent.observation",
        AgentObservation(agent_id=spec.id, tool=tool, summary=outcome.text[:300], ok=outcome.ok),
    )
    observation = ChatMessage.user(f"Observation from {tool}:\n{fence(outcome.text, source=tool)}")
    return {
        "messages": [*state["messages"], observation.model_dump()],
        "sources": [*state.get("sources", []), tool],
    }


async def finalize(state: WorkerState) -> dict[str, Any]:
    """Iteration guard tripped: ask for the best answer from what is known."""
    svc = services()
    spec: AgentSpec = svc.registry.get(state["agent_id"])

    class Final(BaseModel):
        final_answer: str

    msgs = [
        *_messages(state),
        ChatMessage.user(
            "You have used all your steps. Give your best final answer now from the "
            "observations above, and say what is still uncertain."
        ),
    ]
    out = await svc.llm.structured(
        msgs,
        Final,
        purpose="react",
        role=spec.model_role,
        agent_id=spec.id,
        default=Final(final_answer="No conclusive answer within the step limit."),
    )
    emit("agent.final", AgentFinal(agent_id=spec.id, answer=out.final_answer[:2000]))
    return {"final": out.final_answer, "ok": False}


def after_think(state: WorkerState) -> str:
    if state.get("final") is not None:
        return END
    if state.get("iteration", 0) >= state.get("max_iterations", 5):
        return "finalize"
    return "act"


def summariser_for(agent_id: str) -> Any:
    async def summarise(previous: str, old: list[ChatMessage]) -> str:
        transcript = "\n".join(f"{m.role}: {m.content[:800]}" for m in old)
        result = await services().llm.complete(
            [
                ChatMessage.system(
                    "Summarise this agent work log into at most 6 bullet points. Keep every "
                    "fact, number, file name and tool result that may matter later."
                ),
                ChatMessage.user(
                    f"Previous summary:\n{previous or '(none)'}\n\nNew log:\n{transcript}"
                ),
            ],
            purpose="summarise",
            agent_id=agent_id,
            stream=False,
            max_tokens=300,
        )
        return result.content

    return summarise


def build_react_worker() -> CompiledStateGraph[Any, Any, Any, Any]:
    g = StateGraph(WorkerState)
    g.add_node("think", think)
    g.add_node("act", act)
    g.add_node("finalize", finalize)
    g.add_edge(START, "think")
    g.add_conditional_edges("think", after_think, ["act", "finalize", END])
    g.add_edge("act", "think")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=False, name="react_worker")


def initial_worker_state(
    spec: AgentSpec,
    task: str,
    tools: list[str],
    *,
    context: str = "",
    max_iterations: int | None = None,
) -> WorkerState:
    specs = services().toolbox.specs(tools)
    messages = [
        ChatMessage.system(system_prompt(spec, specs)),
        ChatMessage.user(
            f"Your task:\n{task}" + (f"\n\nContext:\n{context}" if context else ""), pinned=True
        ),
    ]
    return WorkerState(
        agent_id=spec.id,
        task=task,
        messages=[m.model_dump() for m in messages],
        tools=tools,
        iteration=0,
        max_iterations=max_iterations or spec.max_steps,
        final=None,
        sources=[],
        summary="",
        ok=True,
    )


react_worker = build_react_worker()
