"""ReAct worker subgraph: Thought → Action → Observation → … → Final.

``think`` asks the agent's model for ONE turn; ``act`` runs the requested tools
through the ToolBox and appends the fenced observations. The two nodes form a cycle
guarded by ``max_iterations``; when the guard trips, ``finalize`` forces an answer
from what was gathered so far.

Two turn formats (``NEXUS_REACT_MODE``):

* ``native`` (default): provider-native function calling. The tools go out as JSON
  Schema (``tools=[...]``), the model answers with structured ``tool_calls``, and each
  result comes back as a ``role="tool"`` message. A reply without tool calls is the
  final answer. Small models sometimes write the call as JSON text instead; that is
  recognised, and an empty reply falls back to one schema-constrained turn.
* ``json``: every turn is schema-constrained JSON (thought + action + action_input,
  or thought + final_answer), the most robust format for 3B models.
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
from nexus.llm.text_tool_calls import (
    FINAL,
    already_made,
    calls_in_text,
    python_style_call,
    text_calls,
)
from nexus.llm.types import ChatMessage, ToolSpec
from nexus.memory.pruning import prune
from nexus.safety.guardrails import UNTRUSTED_RULE, fence


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


def system_prompt(spec: AgentSpec, tools: list[ToolSpec], mode: str = "json") -> str:
    if mode == "native":
        return (
            f"{spec.system_prompt.strip()}\n\n"
            f"You work in ReAct style. Available tools:\n{_describe(tools)}\n\n"
            "Call a tool whenever you need facts instead of guessing; you will get its "
            "result back. When you know enough, reply with your final answer as plain "
            "text (no tool call). Keep final answers factual and concise, and say which "
            "sources you used.\n\n" + UNTRUSTED_RULE
        )
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
    specs = svc.toolbox.specs(state.get("tools", []))
    if svc.settings.react_mode == "native":
        turn = await _native_turn(spec, pruned.messages, specs)
    else:
        turn = await _json_turn(spec, pruned.messages, [t.name for t in specs])
    iteration = state.get("iteration", 0) + 1
    emit("agent.thinking", AgentThinking(agent_id=spec.id, text=turn.thought, iteration=iteration))
    msgs = [m.model_dump() for m in pruned.messages]
    msgs.append(turn.message.model_dump())
    update: dict[str, Any] = {"messages": msgs, "iteration": iteration}
    if pruned.summary:
        update["summary"] = pruned.summary
    if turn.final is not None:
        emit("agent.final", AgentFinal(agent_id=spec.id, answer=turn.final[:2000]))
        update["final"] = turn.final
    return update


class Turn(BaseModel):
    """One model turn, whichever format produced it."""

    thought: str
    message: ChatMessage  # what goes into the history
    final: str | None = None


async def _json_turn(spec: AgentSpec, messages: list[ChatMessage], tool_names: list[str]) -> Turn:
    turn = await services().llm.structured(
        messages,
        _turn_schema(tool_names),
        purpose="react",
        role=spec.model_role,
        agent_id=spec.id,
        temperature=spec.temperature,
    )
    data = turn.model_dump()
    final = None
    if data["action"] == FINAL:
        final = (data.get("final_answer") or data["thought"]).strip()
    return Turn(
        thought=data["thought"], message=ChatMessage.assistant(turn.model_dump_json()), final=final
    )


async def _native_turn(spec: AgentSpec, messages: list[ChatMessage], specs: list[ToolSpec]) -> Turn:
    svc = services()
    result = await svc.llm.complete(
        messages,
        purpose="react",
        role=spec.model_role,
        agent_id=spec.id,
        tools=specs,
        temperature=spec.temperature,
        stream=False,
        max_tokens=900,
    )
    content, calls = result.content.strip(), list(result.tool_calls)
    names = {t.name for t in specs}
    thought = content
    if not calls and content:
        text_thought, calls, final = calls_in_text(content, names)
        if final is not None:
            return Turn(
                thought=text_thought or "Done.", message=ChatMessage.assistant(content), final=final
            )
        if not calls:  # tool(arg=...) in prose, unless it only quotes an earlier call
            prose = python_style_call(content, names)
            if prose and not already_made(prose[0], messages, names):
                text_thought, calls = content, prose
        if calls:  # answered in the text protocol: keep it textual, act parses it
            thought = text_thought or "Calling " + calls[0].name
            return Turn(thought=thought, message=ChatMessage.assistant(content))
    if calls:
        thought = thought or "Calling " + ", ".join(c.name for c in calls)
        message = ChatMessage(role="assistant", content=content, tool_calls=calls)
        return Turn(thought=thought, message=message)
    if content:  # no tool call: this is the final answer
        return Turn(
            thought="I have enough to answer.",
            message=ChatMessage.assistant(content),
            final=content,
        )
    # Empty reply (it happens on 3B models): one schema-constrained turn instead.
    return await _json_turn(spec, messages, sorted(names))


async def act(state: WorkerState) -> dict[str, Any]:
    svc = services()
    spec: AgentSpec = svc.registry.get(state["agent_id"])
    last = ChatMessage.model_validate(state["messages"][-1])
    if last.tool_calls:
        calls, native = last.tool_calls, True
    else:  # JSON turn (json mode, or a call the model wrote as text)
        names = {t.name for t in svc.toolbox.specs(state.get("tools", []))}
        calls, native = text_calls(last.content, names), False
    added: list[dict[str, Any]] = []
    for call in calls:
        tool, args = call.name, call.arguments
        emit(
            "agent.action",
            AgentAction(agent_id=spec.id, tool=tool, args=args, iteration=state.get("iteration")),
        )
        outcome = await svc.toolbox.call(
            tool, args, agent_id=spec.id, allowlist=state.get("tools", [])
        )
        emit(
            "agent.observation",
            AgentObservation(
                agent_id=spec.id, tool=tool, summary=outcome.text[:300], ok=outcome.ok
            ),
        )
        fenced = fence(outcome.text, source=tool)
        observation = (
            ChatMessage.tool(tool, fenced)
            if native
            else ChatMessage.user(f"Observation from {tool}:\n{fenced}")
        )
        added.append(observation.model_dump())
    return {
        "messages": [*state["messages"], *added],
        "sources": [*state.get("sources", []), *(c.name for c in calls)],
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
        ChatMessage.system(system_prompt(spec, specs, services().settings.react_mode)),
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
