"""Token estimation and budgets.

tiktoken does not match Llama/Qwen tokenizers, so NEXUS estimates tokens from
characters *before* a call and learns a per-model correction from Ollama's real
``prompt_eval_count`` *after* it (an exponential moving average). Budgets use the
corrected estimate, and every call logs both numbers so drift is visible.
"""

from __future__ import annotations

import math
import threading

from pydantic import BaseModel, Field

from nexus.llm.types import ChatMessage

CHARS_PER_TOKEN = 3.6  # conservative for English + code on Llama-3/Qwen-2.5 tokenizers
MESSAGE_OVERHEAD = 4  # role markers / separators per chat message


class _Calibration:
    def __init__(self) -> None:
        self._ratio: dict[str, float] = {}
        self._lock = threading.Lock()

    def ratio(self, model: str | None) -> float:
        return self._ratio.get(model or "", 1.0)

    def observe(self, model: str, estimated: int, actual: int) -> None:
        if estimated <= 0 or actual <= 0:
            return
        sample = actual / estimated
        with self._lock:
            prev = self._ratio.get(model, sample)
            self._ratio[model] = min(2.5, max(0.4, 0.8 * prev + 0.2 * sample))


calibration = _Calibration()


def estimate_text(text: str, model: str | None = None) -> int:
    if not text:
        return 0
    return math.ceil(len(text) / CHARS_PER_TOKEN * calibration.ratio(model))


def estimate_messages(messages: list[ChatMessage], model: str | None = None) -> int:
    total = 0
    for m in messages:
        total += estimate_text(m.content, model) + MESSAGE_OVERHEAD
        for c in m.tool_calls:
            total += estimate_text(c.name + str(c.arguments), model)
    return total


class TokenBudget(BaseModel):
    """Per-agent context budget: the model window minus room reserved for the reply."""

    num_ctx: int = 8192
    reserve_output: int = 1024
    used_last_call: int = 0
    total_prompt: int = 0
    total_completion: int = 0
    mission_limit: int = Field(default=50_000, description="Policy cap on tokens per mission.")

    @property
    def window(self) -> int:
        return self.num_ctx - self.reserve_output

    @property
    def total(self) -> int:
        return self.total_prompt + self.total_completion

    def fits(self, tokens: int) -> bool:
        return tokens <= self.window

    def record(self, prompt: int, completion: int) -> TokenBudget:
        return self.model_copy(
            update={
                "used_last_call": prompt,
                "total_prompt": self.total_prompt + prompt,
                "total_completion": self.total_completion + completion,
            }
        )
