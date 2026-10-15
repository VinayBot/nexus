from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from nexus.core.config import get_settings
from nexus.llm.demo_tools import RAW_TOOLS, calculator
from nexus.llm.raw_react_agent import RawReActAgent


def ollama_replies(*contents: str, fail_first: int = 0) -> httpx.MockTransport:
    """Fake /api/chat that returns the given assistant contents in order."""
    queue = list(contents)
    state = {"failures": fail_first}
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if state["failures"] > 0:
            state["failures"] -= 1
            return httpx.Response(503, json={"error": "loading"})
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": queue.pop(0)},
                "prompt_eval_count": 50,
                "eval_count": 10,
            },
        )

    transport = httpx.MockTransport(handler)
    transport.seen = seen  # type: ignore[attr-defined]
    return transport


def agent(transport: httpx.MockTransport, **kw: Any) -> RawReActAgent:
    return RawReActAgent(
        base_url="http://ollama", model="m", tools=RAW_TOOLS, transport=transport, **kw
    )


async def test_raw_agent_thought_action_observation_final() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    transport = ollama_replies(
        '{"thought": "multiply first", "action": "calculator", "action_input": {"expression": "17*23"}}',
        '{"thought": "count letters", "action": "count_letters", "action_input": {"word": "samurai"}}',
        'Here you go: {"thought": "add them", "final_answer": "398"}',
    )
    result = await agent(transport, on_event=lambda k, d: events.append((k, d))).run("task")

    assert result.answer == "398"
    assert result.stopped_reason == "final_answer"
    assert [s.observation for s in result.steps[:2]] == ["391", "7"]
    assert result.llm_calls == 3 and result.prompt_tokens == 150
    assert [k for k, _ in events] == [
        "thought",
        "action",
        "observation",
        "thought",
        "action",
        "observation",
        "thought",
        "final",
    ]
    # the observation is fed back to the model as a user turn
    last_request = transport.seen[-1]  # type: ignore[attr-defined]
    assert last_request["messages"][-1]["content"] == "Observation: 7"
    assert last_request["format"] == "json"


async def test_raw_agent_retries_http_and_reprompts_bad_json() -> None:
    transport = ollama_replies(
        "I think the answer is 4",
        '{"thought": "ok", "final_answer": "4"}',
        fail_first=1,
    )
    result = await agent(transport).run("2+2")
    assert result.answer == "4"
    assert result.retries == 2  # one 503 + one unparsable reply


async def test_raw_agent_unknown_tool_becomes_observation_and_step_limit_holds() -> None:
    loop = '{"thought": "try", "action": "teleport", "action_input": {}}'
    result = await agent(ollama_replies(*[loop] * 3), max_steps=3).run("x")
    assert result.stopped_reason == "max_steps"
    assert result.steps[0].observation is not None
    assert "unknown tool 'teleport'" in result.steps[0].observation


def test_calculator_is_safe() -> None:
    assert calculator("(144 / 12) ** 2 - 40") == "104"
    with pytest.raises(ValueError):
        calculator("__import__('os').system('ls')")


@pytest.mark.live
async def test_raw_agent_against_real_ollama() -> None:
    settings = get_settings()
    result = await RawReActAgent(
        base_url="http://127.0.0.1:11434", model=settings.models.main, tools=RAW_TOOLS
    ).run("What is 17 * 23 plus the number of letters in the word 'samurai'?")
    assert result.answer is not None and "398" in result.answer
