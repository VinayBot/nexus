"""The LangGraph ReAct worker in both turn formats: native tool calling and JSON turns."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest

from nexus.core.config import get_settings
from nexus.core.events import Event, bus
from nexus.core.runtime import runtime
from nexus.core.services import Services
from nexus.llm.scripted import ScriptedLLM, tool_call
from nexus.llm.types import LLMRequest, LLMResult
from tests.fakes import council_llm, local_toolbox


@pytest.fixture(autouse=True)
def native(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests exercise native mode unless they say otherwise ("auto" picks per model)."""
    monkeypatch.setenv("NEXUS_REACT_MODE", "native")
    get_settings.cache_clear()


@pytest.fixture
def events() -> list[Event]:
    captured: list[Event] = []
    bus.reset()
    bus.add_listener(captured.append)
    return captured


async def start(llm: ScriptedLLM) -> AsyncIterator[Services]:
    async with runtime(get_settings(), provider=llm, toolbox=local_toolbox(), recover=False) as svc:
        yield svc


async def findings(svc: Services, task: str) -> list[dict[str, object]]:
    row = await svc.runner.create(task, playbook="council_qa")
    await asyncio.wait_for(svc.runner.wait(row.id), timeout=30)
    state = (await svc.runner.graph.aget_state(svc.runner.config(row.id))).values
    return list(state["findings"])


async def test_native_tool_calls_round_trip(events: list[Event]) -> None:
    """tools=[JSON Schema] out, structured tool_calls in, role="tool" results back."""
    seen: list[LLMRequest] = []

    def react(req: LLMRequest) -> LLMResult | str:
        seen.append(req)
        results = [m for m in req.messages if m.role == "tool"]
        if results:
            assert results[0].tool_name == "knowledge.search"
            assert "merges concurrent updates" in results[0].content  # the real tool output
            return "A reducer merges concurrent updates (source: knowledge.search)."
        return tool_call("knowledge.search", query="reducer")

    async for svc in start(council_llm(react=react)):
        out = await findings(svc, "What is a reducer?")
    assert all(f["ok"] and "merges concurrent" in str(f["summary"]) for f in out)
    first = seen[0]
    assert {t.name for t in first.tools} >= {"knowledge.search"}  # schemas sent natively
    assert first.json_schema is None  # no JSON-format turn in native mode
    assert "plain text" in first.messages[0].content  # the native system prompt
    second = next(r for r in seen if any(m.role == "tool" for m in r.messages))
    calls = [m for m in second.messages if m.role == "assistant" and m.tool_calls]
    assert calls[0].tool_calls[0].arguments == {"query": "reducer"}
    acted = [e for e in events if e.type == "agent.action"]
    assert acted and acted[0].payload["tool"] == "knowledge.search"


async def test_call_written_as_text_is_still_executed(events: list[Event]) -> None:
    """3B models sometimes print {"name": ..., "arguments": ...} instead of a tool call."""

    def react(req: LLMRequest) -> str:
        if any("Observation from knowledge.search" in m.content for m in req.messages):
            return "Reducers merge updates."
        return json.dumps({"name": "knowledge.search", "arguments": {"query": "reducer"}})

    async for svc in start(council_llm(react=react)):
        out = await findings(svc, "What is a reducer?")
    assert all(f["summary"] == "Reducers merge updates." for f in out)
    assert any(e.type == "tool.result" for e in events)


async def test_empty_native_reply_falls_back_to_a_json_turn() -> None:
    final = json.dumps(
        {"thought": "known", "action": "final", "action_input": {}, "final_answer": "Fallback."}
    )

    def react(req: LLMRequest) -> str:
        return final if req.json_schema is not None else ""

    async for svc in start(council_llm(react=react)):
        out = await findings(svc, "What is a reducer?")
    assert all(f["summary"] == "Fallback." for f in out)


async def test_json_mode_uses_schema_constrained_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_REACT_MODE", "json")
    get_settings.cache_clear()
    schemas: list[bool] = []
    from tests.fakes import react_script

    def react(req: LLMRequest) -> str:
        schemas.append(req.json_schema is not None and not req.tools)
        return react_script(req)

    async for svc in start(council_llm(react=react)):
        out = await findings(svc, "What is a reducer?")
    get_settings.cache_clear()
    assert schemas and all(schemas)
    assert all("Reducers merge" in str(f["summary"]) for f in out)


@pytest.mark.live
@pytest.mark.parametrize("model", ["qwen2.5:3b", "llama3.2:3b"])
async def test_native_worker_against_real_ollama(
    model: str, monkeypatch: pytest.MonkeyPatch, events: list[Event]
) -> None:
    """The LangGraph worker drives a real local model through native tool calls."""
    from nexus.graph.subgraphs.react_worker import initial_worker_state, react_worker
    from nexus.llm.ollama_provider import OllamaProvider

    monkeypatch.setenv("NEXUS_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("NEXUS_MODEL_MAIN", model)
    get_settings.cache_clear()
    provider = OllamaProvider("http://127.0.0.1:11434")
    async with runtime(get_settings(), provider=provider, toolbox=local_toolbox(), recover=False):
        from nexus.core.services import services

        spec = services().registry.get("echo")
        state = initial_worker_state(
            spec,
            "What is 17 * 23 plus the number of letters in the word 'android'? Use the tools.",
            ["demo.calculator", "demo.count_letters"],
        )
        out = await react_worker.ainvoke(state)
    get_settings.cache_clear()
    used = {e.payload["tool"] for e in events if e.type == "agent.action"}
    assert used & {"demo.calculator", "demo.count_letters"}
    assert "398" in (out["final"] or "")


def test_text_tool_call_parsing() -> None:
    from nexus.llm.text_tool_calls import already_made, calls_in_text, python_style_call
    from nexus.llm.types import ChatMessage, ToolCall

    names = {"demo.calculator"}
    turn = '{"thought": "t", "action": "demo.calculator", "action_input": {"expression": "2*3"}}'
    assert calls_in_text(turn, names)[1] == [
        ToolCall(name="demo.calculator", arguments={"expression": "2*3"})
    ]
    assert calls_in_text('{"name": "rm_rf", "arguments": {}}', names)[1] == []  # unknown tool
    assert calls_in_text('{"action": "final", "final_answer": "6"}', names)[2] == "6"
    prose = 'I will run demo.calculator(expression="17 * 23") now.'
    call = python_style_call(prose, names)[0]
    assert call.arguments == {"expression": "17 * 23"}
    history = [ChatMessage(role="assistant", content="", tool_calls=[call])]
    assert already_made(call, history, names)
    assert not already_made(call, [ChatMessage.user(prose)], names)


async def test_auto_mode_follows_the_benchmark(monkeypatch: pytest.MonkeyPatch) -> None:
    from nexus.graph.subgraphs.react_worker import react_mode

    monkeypatch.setenv("NEXUS_REACT_MODE", "auto")
    get_settings.cache_clear()
    async for svc in start(council_llm()):
        svc.llm.router.models = svc.llm.router.models.model_copy(update={"main": "llama3.2:3b"})
        assert react_mode() == "json"
        svc.llm.router.models = svc.llm.router.models.model_copy(update={"main": "qwen2.5:3b"})
        assert react_mode() == "native"
