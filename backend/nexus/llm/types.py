"""Provider-neutral chat types used by every LLM caller in NEXUS."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]
ModelRole = Literal["main", "fast"]


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    id: str | None = None


class ChatMessage(BaseModel):
    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_name: str | None = None
    #: Pinned messages survive sliding-window pruning (plan, current step, key findings).
    pinned: bool = False

    @classmethod
    def system(cls, content: str) -> ChatMessage:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str, *, pinned: bool = False) -> ChatMessage:
        return cls(role="user", content=content, pinned=pinned)

    @classmethod
    def assistant(cls, content: str) -> ChatMessage:
        return cls(role="assistant", content=content)

    @classmethod
    def tool(cls, name: str, content: str) -> ChatMessage:
        return cls(role="tool", content=content, tool_name=name)


class ToolSpec(BaseModel):
    """A tool offered to the model (JSON-Schema parameters, OpenAI/Ollama style)."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})

    def to_ollama(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class LLMRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    tools: list[ToolSpec] = Field(default_factory=list)
    temperature: float = 0.2
    num_ctx: int = 8192
    max_tokens: int | None = None
    json_schema: dict[str, Any] | None = None
    #: Free-form label ("planner", "rewrite", "judge"...) used for routing, events and fakes.
    purpose: str = "chat"
    agent_id: str | None = None


class LLMResult(BaseModel):
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: float = 0.0

    @property
    def tokens_per_sec(self) -> float:
        if self.duration_ms <= 0:
            return 0.0
        return self.completion_tokens / (self.duration_ms / 1000)


TokenCallback = Callable[[str], Awaitable[None] | None]
