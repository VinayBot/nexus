"""Deterministic fake provider for tests and the labelled Simulation mode.

Responses are chosen by ``purpose`` (the label every caller attaches to a request).
A rule is either a fixed string/LLMResult, a list consumed in order, or a callable
that sees the full request — enough to script whole missions offline.
"""

from __future__ import annotations

import hashlib
import inspect
import math
from collections.abc import Callable
from typing import Any

from nexus.llm.provider import ProviderError
from nexus.llm.types import LLMRequest, LLMResult, TokenCallback, ToolCall

Rule = str | LLMResult | list[str | LLMResult] | Callable[[LLMRequest], str | LLMResult]


class ScriptedLLM:
    name = "scripted"

    def __init__(self, rules: dict[str, Rule] | None = None, *, default: str = "OK") -> None:
        self.rules: dict[str, Rule] = dict(rules or {})
        self.default = default
        self.calls: list[LLMRequest] = []
        #: purpose -> number of upcoming calls that should raise a retryable error
        self.failures: dict[str, int] = {}

    def on(self, purpose: str, rule: Rule) -> ScriptedLLM:
        self.rules[purpose] = rule
        return self

    def fail_next(self, purpose: str, times: int = 1) -> None:
        self.failures[purpose] = self.failures.get(purpose, 0) + times

    def _pick(self, request: LLMRequest) -> str | LLMResult:
        rule = self.rules.get(request.purpose, self.rules.get("*", self.default))
        if isinstance(rule, list):
            if not rule:
                return self.default
            return rule.pop(0) if len(rule) > 1 else rule[0]
        if callable(rule) and not isinstance(rule, LLMResult):
            return rule(request)
        return rule

    async def chat(self, request: LLMRequest, on_token: TokenCallback | None = None) -> LLMResult:
        self.calls.append(request)
        if self.failures.get(request.purpose, 0) > 0:
            self.failures[request.purpose] -= 1
            raise ProviderError(f"scripted failure for {request.purpose}", retryable=True)
        out = self._pick(request)
        result = out if isinstance(out, LLMResult) else LLMResult(content=out, model=request.model)
        if not result.prompt_tokens:
            prompt = sum(len(m.content) for m in request.messages)
            result = result.model_copy(
                update={
                    "prompt_tokens": max(1, prompt // 4),
                    "completion_tokens": max(1, len(result.content) // 4),
                    "duration_ms": 5.0,
                }
            )
        if on_token and result.content:
            res = on_token(result.content)
            if inspect.isawaitable(res):
                await res
        return result

    async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        return [hash_embedding(t) for t in texts]

    async def loaded_models(self) -> list[dict[str, Any]]:
        return [{"name": "scripted", "size_gb": 0.0, "vram_gb": 0.0, "context_length": 8192}]

    async def available_models(self) -> list[str]:
        return ["scripted"]


def tool_call(name: str, **arguments: Any) -> LLMResult:
    """Helper: a scripted response that calls a tool natively."""
    return LLMResult(content="", tool_calls=[ToolCall(name=name, arguments=arguments)], model="x")


def hash_embedding(text: str, dims: int = 64) -> list[float]:
    """Bag-of-words hashing embedding: similar texts share dimensions. Unit length."""
    vec = [0.0] * dims
    for word in text.lower().split():
        h = int(hashlib.md5(word.encode(), usedforsecurity=False).hexdigest(), 16)
        vec[h % dims] += 1.0 if (h >> 8) & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]
