"""Context pruning: keep each agent's prompt inside its token budget.

Two strategies, both preserving the system prompt and *pinned* messages (the
task, plan and current step):

* **sliding_window** — drop the oldest unpinned turns until the prompt fits,
  always keeping at least the last ``keep_last`` turns.
* **summarise** — fold the oldest unpinned turns into a rolling summary written
  by the fast model, then keep the recent window. Falls back to sliding window if
  the summary call fails.

Both emit ``memory.pruned`` / ``memory.summarised`` with before/after token counts.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from nexus.core.event_types import MemoryPruned, MemorySummarised
from nexus.core.events import emit
from nexus.llm.tokens import estimate_messages
from nexus.llm.types import ChatMessage

Strategy = Literal["sliding_window", "summarise"]
Summariser = Callable[[str, list[ChatMessage]], Awaitable[str]]

SUMMARY_PREFIX = "Summary of earlier work (older turns were folded to save context):\n"


@dataclass
class PruneResult:
    messages: list[ChatMessage]
    summary: str
    before: int
    after: int
    dropped: int

    @property
    def pruned(self) -> bool:
        return self.dropped > 0


def _split(messages: list[ChatMessage]) -> tuple[list[ChatMessage], list[ChatMessage]]:
    keep = [m for m in messages if m.role == "system" or m.pinned]
    rest = [m for m in messages if not (m.role == "system" or m.pinned)]
    return keep, rest


def _assemble(
    messages: list[ChatMessage], keep: list[ChatMessage], window: list[ChatMessage]
) -> list[ChatMessage]:
    chosen = {id(m) for m in keep} | {id(m) for m in window}
    return [m for m in messages if id(m) in chosen]


def sliding_window(
    messages: list[ChatMessage], budget: int, *, keep_last: int = 2, model: str | None = None
) -> PruneResult:
    before = estimate_messages(messages, model)
    if before <= budget:
        return PruneResult(messages, "", before, before, 0)
    keep, rest = _split(messages)
    window = list(rest)
    while len(window) > keep_last and estimate_messages(keep + window, model) > budget:
        window.pop(0)
    out = _assemble(messages, keep, window)
    return PruneResult(out, "", before, estimate_messages(out, model), len(rest) - len(window))


async def summarise(
    messages: list[ChatMessage],
    budget: int,
    summariser: Summariser,
    *,
    previous_summary: str = "",
    keep_last: int = 2,
    model: str | None = None,
) -> PruneResult:
    before = estimate_messages(messages, model)
    if before <= budget:
        return PruneResult(messages, previous_summary, before, before, 0)
    keep, rest = _split(messages)
    # keep the most recent turns that fit in ~half the budget; fold everything older
    window: list[ChatMessage] = []
    for m in reversed(rest):
        if len(window) >= keep_last and estimate_messages(keep + window + [m], model) > budget // 2:
            break
        window.insert(0, m)
    old = rest[: len(rest) - len(window)]
    if not old:
        return sliding_window(messages, budget, keep_last=keep_last, model=model)
    summary = (await summariser(previous_summary, old)).strip()
    summary_msg = ChatMessage.user(SUMMARY_PREFIX + summary, pinned=True)
    # drop any earlier summary message; the new one supersedes it
    keep = [m for m in keep if not m.content.startswith(SUMMARY_PREFIX)]
    head = [m for m in messages if m in keep]
    out = [*head, summary_msg, *window]
    out_tokens = estimate_messages(out, model)
    if out_tokens > budget:  # summary itself too long: trim the window further
        fallback = sliding_window(out, budget, keep_last=1, model=model)
        out, out_tokens = fallback.messages, fallback.after
    return PruneResult(out, summary, before, out_tokens, len(old))


async def prune(
    messages: list[ChatMessage],
    budget: int,
    *,
    agent_id: str,
    strategy: Strategy,
    summariser: Summariser | None = None,
    previous_summary: str = "",
    model: str | None = None,
) -> PruneResult:
    """Apply ``strategy`` and emit events; never raises because of the summariser."""
    result: PruneResult
    if strategy == "summarise" and summariser is not None:
        try:
            result = await summarise(
                messages, budget, summariser, previous_summary=previous_summary, model=model
            )
            if result.pruned and result.summary:
                emit(
                    "memory.summarised",
                    MemorySummarised(
                        agent_id=agent_id,
                        before_tokens=result.before,
                        after_tokens=result.after,
                        summary=result.summary[:600],
                    ),
                )
        except Exception:
            result = sliding_window(messages, budget, model=model)
            strategy = "sliding_window"
    else:
        result = sliding_window(messages, budget, model=model)
        strategy = "sliding_window"
    if result.pruned:
        emit(
            "memory.pruned",
            MemoryPruned(
                agent_id=agent_id,
                strategy=strategy,
                before_tokens=result.before,
                after_tokens=result.after,
                dropped_messages=result.dropped,
                budget=budget,
            ),
        )
    return result
