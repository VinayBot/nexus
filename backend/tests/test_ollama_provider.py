"""OllamaProvider against the real ``ollama`` client and an in-memory HTTP transport: the
wire format (tools, tool calls, streaming, embeddings) and error classification."""

from __future__ import annotations

import json
from typing import Any

import httpx
import ollama
import pytest

from nexus.llm.ollama_provider import OllamaProvider
from nexus.llm.provider import ProviderError
from nexus.llm.types import ChatMessage, LLMRequest, ToolCall, ToolSpec

SPEC = ToolSpec(
    name="demo.calculator",
    description="Evaluate arithmetic.",
    parameters={"type": "object", "properties": {"expression": {"type": "string"}}},
)


def provider(handler: Any) -> tuple[OllamaProvider, list[dict[str, Any]]]:
    seen: list[dict[str, Any]] = []

    def record(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        seen.append({"path": request.url.path, **body})
        return handler(request.url.path, body)

    p = OllamaProvider("http://ollama.test")
    p._client = ollama.AsyncClient(host="http://ollama.test", transport=httpx.MockTransport(record))
    return p, seen


def request(**kw: Any) -> LLMRequest:
    return LLMRequest(
        model="qwen2.5:3b",
        messages=[ChatMessage.system("s"), ChatMessage.user("What is 6 * 7?")],
        purpose="react",
        **kw,
    )


def done(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": "qwen2.5:3b",
        "created_at": "2026-10-21T00:00:00Z",
        "message": message,
        "done": True,
        "prompt_eval_count": 12,
        "eval_count": 5,
    }


async def test_tools_go_out_as_schema_and_tool_calls_come_back() -> None:
    call = {"function": {"name": "demo.calculator", "arguments": {"expression": "6*7"}}}
    p, seen = provider(
        lambda path, body: httpx.Response(
            200, json=done({"role": "assistant", "content": "", "tool_calls": [call]})
        )
    )
    history = [
        ChatMessage.user("hi"),
        ChatMessage(role="assistant", content="", tool_calls=[ToolCall(name="a", arguments={})]),
        ChatMessage.tool("a", "42"),
    ]
    out = await p.chat(request(tools=[SPEC]).model_copy(update={"messages": history}))
    assert out.tool_calls == [ToolCall(name="demo.calculator", arguments={"expression": "6*7"})]
    assert (out.prompt_tokens, out.completion_tokens) == (12, 5)
    sent = seen[0]
    assert sent["tools"][0]["function"]["name"] == "demo.calculator"
    assert sent["messages"][1]["tool_calls"][0]["function"]["name"] == "a"
    assert sent["messages"][2] == {"role": "tool", "content": "42", "tool_name": "a"}


async def test_streaming_feeds_tokens_and_json_schema_is_sent_as_format() -> None:
    chunks = [
        {"model": "m", "created_at": "t", "message": {"role": "assistant", "content": "4"}},
        {"model": "m", "created_at": "t", "message": {"role": "assistant", "content": "2"}},
        done({"role": "assistant", "content": ""}),
    ]
    body = "\n".join(json.dumps(c) for c in chunks) + "\n"
    p, seen = provider(lambda path, b: httpx.Response(200, text=body))
    tokens: list[str] = []
    schema = {"type": "object", "properties": {"n": {"type": "integer"}}}
    out = await p.chat(request(json_schema=schema, max_tokens=50), on_token=tokens.append)
    assert tokens == ["4", "2"] and out.content == "42"
    assert seen[0]["format"] == schema and seen[0]["options"]["num_predict"] == 50
    assert seen[0]["stream"] is True


async def test_errors_are_classified_for_the_retry_layer() -> None:
    missing, _ = provider(lambda path, b: httpx.Response(404, json={"error": "model not found"}))
    with pytest.raises(ProviderError) as not_found:
        await missing.chat(request())
    assert not not_found.value.retryable  # a missing model will not appear by retrying

    busy, _ = provider(lambda path, b: httpx.Response(500, json={"error": "overloaded"}))
    with pytest.raises(ProviderError) as server:
        await busy.chat(request())
    assert server.value.retryable

    def down(path: str, b: Any) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    offline, _ = provider(down)
    with pytest.raises(ProviderError) as unreachable:
        await offline.embed("nomic-embed-text", ["x"])
    assert unreachable.value.retryable
    assert await offline.loaded_models() == []  # Ollama down: nothing is loaded


async def test_embeddings_models_and_unload() -> None:
    def handler(path: str, body: Any) -> httpx.Response:
        if path == "/api/embed":
            return httpx.Response(200, json={"model": "e", "embeddings": [[0.1, 0.2]]})
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [{"model": "qwen2.5:3b", "name": "q"}]})
        if path == "/api/ps":
            model = {"model": "qwen2.5:3b", "size": 2_000_000_000, "size_vram": 1_000_000_000}
            return httpx.Response(200, json={"models": [{**model, "context_length": 8192}]})
        return httpx.Response(
            200, json={"model": "m", "created_at": "t", "response": "", "done": True}
        )

    p, seen = provider(handler)
    assert await p.embed("nomic-embed-text", ["hello"]) == [[0.1, 0.2]]
    assert await p.available_models() == ["qwen2.5:3b"]
    loaded = await p.loaded_models()
    assert loaded[0]["name"] == "qwen2.5:3b" and loaded[0]["size_gb"] == 2.0
    await p.unload("qwen2.5:3b")
    assert seen[-1]["path"] == "/api/generate" and seen[-1]["keep_alive"] == 0
