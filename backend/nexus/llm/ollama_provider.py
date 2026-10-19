"""Ollama implementation of :class:`LLMProvider` using the official ``ollama`` client."""

from __future__ import annotations

import inspect
import time
from typing import Any

import httpx
import ollama

from nexus.llm.provider import ProviderError
from nexus.llm.types import LLMRequest, LLMResult, TokenCallback, ToolCall


def _to_wire(request: LLMRequest) -> list[dict[str, Any]]:
    wire: list[dict[str, Any]] = []
    for m in request.messages:
        msg: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.tool_calls:
            msg["tool_calls"] = [
                {"function": {"name": c.name, "arguments": c.arguments}} for c in m.tool_calls
            ]
        if m.tool_name:
            msg["tool_name"] = m.tool_name
        wire.append(msg)
    return wire


def _classify(exc: Exception) -> ProviderError:
    if isinstance(exc, ollama.ResponseError):
        status = getattr(exc, "status_code", 500) or 500
        # 404 model missing / 400 bad request are not worth retrying
        return ProviderError(f"ollama {status}: {exc.error}", retryable=status >= 500)
    if isinstance(exc, httpx.TimeoutException | TimeoutError):
        return ProviderError(f"ollama timeout: {exc!s}", retryable=True)
    if isinstance(exc, httpx.TransportError | ConnectionError):
        return ProviderError(f"ollama unreachable: {exc!s}", retryable=True)
    return ProviderError(f"ollama error: {exc!r}", retryable=False)


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, *, timeout_s: float = 180.0, keep_alive: str = "30m") -> None:
        self._client = ollama.AsyncClient(host=base_url, timeout=timeout_s)
        self._keep_alive = keep_alive

    async def chat(self, request: LLMRequest, on_token: TokenCallback | None = None) -> LLMResult:
        options: dict[str, Any] = {"temperature": request.temperature, "num_ctx": request.num_ctx}
        if request.max_tokens:
            options["num_predict"] = request.max_tokens
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": _to_wire(request),
            "options": options,
            "keep_alive": self._keep_alive,
        }
        if request.tools:
            kwargs["tools"] = [t.to_ollama() for t in request.tools]
        if request.json_schema is not None:
            kwargs["format"] = request.json_schema

        started = time.perf_counter()
        content: list[str] = []
        calls: list[ToolCall] = []
        prompt_tokens = completion_tokens = 0
        try:
            # Tool calls are only reliable non-streamed on small models.
            if on_token is not None and not request.tools:
                async for chunk in await self._client.chat(stream=True, **kwargs):
                    piece = chunk.message.content or ""
                    if piece:
                        content.append(piece)
                        res = on_token(piece)
                        if inspect.isawaitable(res):
                            await res
                    if chunk.done:
                        prompt_tokens = chunk.prompt_eval_count or 0
                        completion_tokens = chunk.eval_count or 0
            else:
                resp = await self._client.chat(stream=False, **kwargs)
                content.append(resp.message.content or "")
                for c in resp.message.tool_calls or []:
                    calls.append(
                        ToolCall(name=c.function.name, arguments=dict(c.function.arguments))
                    )
                prompt_tokens = resp.prompt_eval_count or 0
                completion_tokens = resp.eval_count or 0
                if on_token and content[0]:
                    res = on_token(content[0])
                    if inspect.isawaitable(res):
                        await res
        except ProviderError:
            raise
        except Exception as exc:
            raise _classify(exc) from exc

        return LLMResult(
            content="".join(content),
            tool_calls=calls,
            model=request.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    async def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        try:
            resp = await self._client.embed(model=model, input=texts, keep_alive=self._keep_alive)
        except Exception as exc:
            raise _classify(exc) from exc
        return [list(v) for v in resp.embeddings]

    async def pull(self, model: str, progress: Any = None) -> None:
        """Download a model, reporting (status, completed_bytes, total_bytes)."""
        try:
            async for part in await self._client.pull(model, stream=True):
                if progress is not None:
                    progress(part.status or "", part.completed or 0, part.total or 0)
        except Exception as exc:
            raise _classify(exc) from exc

    async def unload(self, model: str) -> None:
        """Free a model's memory now instead of waiting for keep_alive to expire."""
        try:
            await self._client.generate(model=model, prompt="", keep_alive=0)
        except Exception as exc:
            raise _classify(exc) from exc

    async def loaded_models(self) -> list[dict[str, Any]]:
        try:
            resp = await self._client.ps()
        except Exception:
            return []
        return [
            {
                "name": m.model or m.name,
                "size_gb": round((m.size or 0) / 1e9, 2),
                "vram_gb": round((m.size_vram or 0) / 1e9, 2),
                "context_length": m.context_length,
            }
            for m in resp.models
        ]

    async def available_models(self) -> list[str]:
        try:
            resp = await self._client.list()
        except Exception as exc:
            raise _classify(exc) from exc
        return [m.model for m in resp.models if m.model]
