"""LLM gateway: the single door every LLM call in NEXUS goes through.

Layers, outermost first:

1. Model Router chooses the model (fast/main) for the call's purpose.
2. Fallback chain: primary model → alternate model → primary with reduced context.
3. Circuit breaker per model fails fast while a model is unhealthy.
4. Transport retries (tenacity, exponential backoff + jitter).
5. Resource Governor slot + per-call timeout.

``structured()`` adds JSON repair, Pydantic validation, re-prompting with the exact
validation error, escalation to the main model, and an optional safe default.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from nexus.core.event_types import AgentToken, LlmCall, Retry
from nexus.core.events import agent_context, emit
from nexus.core.governor import ResourceGovernor
from nexus.core.logging import get_logger
from nexus.llm.provider import LLMProvider, ProviderError
from nexus.llm.router import ModelRouter
from nexus.llm.tokens import calibration, estimate_messages
from nexus.llm.types import ChatMessage, LLMRequest, LLMResult, ModelRole, ToolSpec
from nexus.reliability.circuit_breaker import BreakerRegistry, CircuitOpenError
from nexus.reliability.json_repair import JsonRepairError, extract_json
from nexus.reliability.retry import with_retries

log = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    pass


class LLMUnavailableError(RuntimeError):
    pass


class TokenStreamer:
    """Coalesces streamed tokens into ``agent.token`` events (~every 120 ms)."""

    def __init__(self, agent_id: str, purpose: str, interval_s: float = 0.12) -> None:
        self.agent_id = agent_id
        self.purpose = purpose
        self.interval = interval_s
        self._buf: list[str] = []
        self._last = time.monotonic()

    def __call__(self, piece: str) -> None:
        self._buf.append(piece)
        if time.monotonic() - self._last >= self.interval:
            self.flush()

    def flush(self) -> None:
        if self._buf:
            text = "".join(self._buf)
            self._buf.clear()
            emit("agent.token", AgentToken(agent_id=self.agent_id, text=text, purpose=self.purpose))
        self._last = time.monotonic()


def reduce_context(messages: list[ChatMessage], keep_last: int = 2) -> list[ChatMessage]:
    """Last-resort context: system prompt(s), pinned messages and the final turns."""
    head = [m for m in messages if m.role == "system" or m.pinned]
    tail = [m for m in messages[-keep_last:] if m not in head]
    return head + tail


class LLMGateway:
    def __init__(
        self,
        provider: LLMProvider,
        router: ModelRouter,
        governor: ResourceGovernor,
        breakers: BreakerRegistry,
        *,
        num_ctx: int = 8192,
        timeout_s: float = 180.0,
        fallback_model: str | None = None,
        embed_model: str = "nomic-embed-text",
        retry_initial_s: float = 0.5,
    ) -> None:
        self.retry_initial_s = retry_initial_s
        self.provider = provider
        self.router = router
        self.governor = governor
        self.breakers = breakers
        self.num_ctx = num_ctx
        self.timeout_s = timeout_s
        self.fallback_model = fallback_model
        self.embed_model = embed_model

    # -- single attempt against one model --------------------------------------------
    async def _call_model(self, request: LLMRequest, stream: bool) -> LLMResult:
        breaker = self.breakers.get(f"model:{request.model}")
        breaker.before_call()
        streamer = (
            TokenStreamer(request.agent_id, request.purpose)
            if (stream and request.agent_id)
            else None
        )

        async def attempt() -> LLMResult:
            async with self.governor.slot(request.model):
                async with asyncio.timeout(self.timeout_s):
                    return await self.provider.chat(request, on_token=streamer)

        try:
            result = await with_retries(
                attempt,
                key=f"model:{request.model}",
                agent_id=request.agent_id,
                initial_s=self.retry_initial_s,
            )
        except Exception:
            breaker.on_failure()
            raise
        finally:
            if streamer:
                streamer.flush()
        breaker.on_success()
        return result

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        purpose: str,
        role: ModelRole | None = None,
        agent_id: str | None = None,
        tools: list[ToolSpec] | None = None,
        temperature: float = 0.2,
        json_schema: dict[str, Any] | None = None,
        num_ctx: int | None = None,
        max_tokens: int | None = None,
        stream: bool = True,
        validation_failures: int = 0,
    ) -> LLMResult:
        agent_id = agent_id or agent_context.get()
        _, primary = self.router.pick(purpose, role=role, validation_failures=validation_failures)
        base = LLMRequest(
            model=primary,
            messages=messages,
            tools=tools or [],
            temperature=temperature,
            num_ctx=num_ctx or self.num_ctx,
            max_tokens=max_tokens,
            json_schema=json_schema,
            purpose=purpose,
            agent_id=agent_id,
        )
        chain: list[tuple[str, LLMRequest]] = [("primary", base)]
        if self.fallback_model and self.fallback_model != primary:
            chain.append(
                ("alternate model", base.model_copy(update={"model": self.fallback_model}))
            )
        if len(messages) > 3:
            chain.append(
                ("reduced context", base.model_copy(update={"messages": reduce_context(messages)}))
            )

        last_exc: Exception | None = None
        for i, (label, req) in enumerate(chain):
            if i > 0:
                emit(
                    "retry",
                    Retry(
                        layer="fallback",
                        key=f"model:{req.model}",
                        attempt=i + 1,
                        max_attempts=len(chain),
                        reason=f"fallback to {label}: {last_exc!s}"[:300],
                        agent_id=agent_id,
                    ),
                )
            estimated = estimate_messages(req.messages, req.model)
            try:
                result = await self._call_model(req, stream)
            except (ProviderError, CircuitOpenError, TimeoutError) as exc:
                last_exc = exc
                log.warning("llm.attempt_failed", model=req.model, step=label, error=str(exc))
                continue
            self._account(req, result, estimated)
            return result
        raise LLMUnavailableError(f"all fallbacks failed for '{purpose}': {last_exc!s}")

    def _account(self, req: LLMRequest, result: LLMResult, estimated: int) -> None:
        calibration.observe(req.model, estimated, result.prompt_tokens)
        self.governor.record_generation(result.completion_tokens, result.duration_ms / 1000)
        emit(
            "llm.call",
            LlmCall(
                model=result.model,
                purpose=req.purpose,
                agent_id=req.agent_id,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                estimated_prompt_tokens=estimated,
                duration_ms=round(result.duration_ms, 1),
                tokens_per_sec=round(result.tokens_per_sec, 1),
            ),
        )

    # -- structured output ------------------------------------------------------------
    async def structured(
        self,
        messages: list[ChatMessage],
        schema: type[T],
        *,
        purpose: str,
        role: ModelRole | None = None,
        agent_id: str | None = None,
        temperature: float = 0.1,
        max_reprompts: int = 2,
        default: T | None = None,
    ) -> T:
        """Return a validated ``schema`` instance (or ``default``), re-prompting on errors."""
        convo = list(messages)
        json_schema = schema.model_json_schema()
        failures = 0
        # 1 attempt + N re-prompts; the router moves a fast call to the main model
        # once it has failed validation twice.
        attempts = max_reprompts + 1
        last_error = ""
        for attempt in range(1, attempts + 1):
            result = await self.complete(
                convo,
                purpose=purpose,
                role=role,
                agent_id=agent_id,
                temperature=temperature,
                json_schema=json_schema,
                stream=False,
                validation_failures=failures,
            )
            try:
                return schema.model_validate(extract_json(result.content))
            except (JsonRepairError, ValidationError) as exc:
                failures += 1
                last_error = _short_error(exc)
                if attempt < attempts:
                    emit(
                        "retry",
                        Retry(
                            layer="validation",
                            key=f"schema:{schema.__name__}",
                            attempt=attempt + 1,
                            max_attempts=attempts,
                            reason=last_error,
                            agent_id=agent_id or agent_context.get(),
                        ),
                    )
                convo = [
                    *convo,
                    ChatMessage.assistant(result.content[:2000]),
                    ChatMessage.user(
                        "Your previous reply was not valid. Error:\n"
                        f"{last_error}\n"
                        f"Reply with ONLY a JSON object matching this schema:\n{json_schema}"
                    ),
                ]
        if default is not None:
            emit(
                "retry",
                Retry(
                    layer="fallback",
                    key=f"schema:{schema.__name__}",
                    attempt=attempts,
                    max_attempts=attempts,
                    reason=f"using safe default after: {last_error}"[:300],
                    agent_id=agent_id or agent_context.get(),
                ),
            )
            return default
        raise StructuredOutputError(f"{schema.__name__}: {last_error}")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async def attempt() -> list[list[float]]:
            async with self.governor.slot(self.embed_model):
                return await self.provider.embed(self.embed_model, texts)

        return await with_retries(attempt, key=f"model:{self.embed_model}")


def _short_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts = [
            f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}"
            for e in exc.errors()[:5]
        ]
        return "; ".join(parts)
    return str(exc)[:300]
