"""Per-dependency circuit breakers (closed → open → half-open → closed).

After ``threshold`` consecutive failures a breaker opens and fails fast for
``cooldown_s``; then one trial call is allowed (half-open). Success closes it,
failure re-opens it. Every transition emits a ``circuit.state`` event.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from nexus.core.event_types import CircuitState
from nexus.core.events import emit

State = Literal["closed", "open", "half_open"]


class CircuitOpenError(RuntimeError):
    def __init__(self, key: str, retry_in: float) -> None:
        super().__init__(f"circuit '{key}' is open; retry in {retry_in:.1f}s")
        self.key = key
        self.retry_in = retry_in


@dataclass
class CircuitBreaker:
    key: str
    threshold: int = 3
    cooldown_s: float = 20.0
    state: State = "closed"
    failures: int = 0
    opened_at: float = 0.0
    trial_in_flight: bool = False
    clock: object = field(default=time.monotonic, repr=False)

    def _now(self) -> float:
        return self.clock()  # type: ignore[operator, no-any-return]

    def _set(self, state: State) -> None:
        if state != self.state:
            self.state = state
            emit("circuit.state", CircuitState(key=self.key, state=state, failures=self.failures))

    def before_call(self) -> None:
        """Raise CircuitOpenError if calls are currently refused."""
        if self.state == "open":
            elapsed = self._now() - self.opened_at
            if elapsed < self.cooldown_s:
                raise CircuitOpenError(self.key, self.cooldown_s - elapsed)
            self._set("half_open")
        if self.state == "half_open":
            if self.trial_in_flight:
                raise CircuitOpenError(self.key, 1.0)
            self.trial_in_flight = True

    def on_success(self) -> None:
        self.trial_in_flight = False
        self.failures = 0
        self._set("closed")

    def on_failure(self) -> None:
        self.trial_in_flight = False
        self.failures += 1
        if self.state == "half_open" or self.failures >= self.threshold:
            self.opened_at = self._now()
            self._set("open")


class BreakerRegistry:
    def __init__(self, threshold: int = 3, cooldown_s: float = 20.0) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self.threshold = threshold
        self.cooldown_s = cooldown_s

    def get(self, key: str) -> CircuitBreaker:
        if key not in self._breakers:
            self._breakers[key] = CircuitBreaker(key, self.threshold, self.cooldown_s)
        return self._breakers[key]

    def snapshot(self) -> list[dict[str, object]]:
        return [
            {"key": b.key, "state": b.state, "failures": b.failures}
            for b in sorted(self._breakers.values(), key=lambda b: b.key)
        ]


breakers = BreakerRegistry()
