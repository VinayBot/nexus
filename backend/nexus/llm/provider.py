"""The ``LLMProvider`` interface every backend (Ollama, scripted fake, MLX…) implements."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from nexus.llm.types import LLMRequest, LLMResult, TokenCallback


class ProviderError(Exception):
    """A provider failure. ``retryable`` tells the reliability layer whether to retry."""

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def chat(self, request: LLMRequest, on_token: TokenCallback | None = None) -> LLMResult:
        """One chat completion. Streams text through ``on_token`` when given."""
        ...

    async def embed(self, model: str, texts: list[str]) -> list[list[float]]: ...

    async def loaded_models(self) -> list[dict[str, Any]]:
        """Models currently resident in memory (name, size_gb...)."""
        ...

    async def available_models(self) -> list[str]: ...
