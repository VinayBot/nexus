"""Transport-level retries: tenacity exponential backoff with jitter, made observable.

Each retry emits a ``retry`` event, which the UI turns into the dizzy-robot
animation with an attempt counter.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from nexus.core.event_types import Retry
from nexus.core.events import emit
from nexus.llm.provider import ProviderError

T = TypeVar("T")


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, ProviderError):
        return exc.retryable
    return isinstance(exc, TimeoutError | ConnectionError)


async def with_retries[T](
    fn: Callable[[], Awaitable[T]],
    *,
    key: str,
    attempts: int = 3,
    initial_s: float = 0.5,
    max_s: float = 8.0,
    layer: Literal["transport", "tool"] = "transport",
    agent_id: str | None = None,
    retry_on: Callable[[BaseException], bool] = is_retryable,
) -> T:
    def before_sleep(state: RetryCallState) -> None:
        exc = state.outcome.exception() if state.outcome else None
        emit(
            "retry",
            Retry(
                layer=layer,
                key=key,
                attempt=state.attempt_number + 1,
                max_attempts=attempts,
                reason=str(exc)[:300] if exc else "unknown",
                agent_id=agent_id,
            ),
        )

    retrying = AsyncRetrying(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential_jitter(multiplier=initial_s, max=max_s, jitter=initial_s),
        retry=retry_if_exception(retry_on),
        before_sleep=before_sleep,
        reraise=True,
    )
    async for attempt in retrying:
        with attempt:
            return await fn()
    raise AssertionError("unreachable")  # pragma: no cover
