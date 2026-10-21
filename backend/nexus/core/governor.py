"""Resource Governor — keeps a 16 GB laptop responsive while agents run.

* An adaptive admission limit caps concurrent LLM calls (global + per model).
* A monitor samples free memory; under pressure the limit drops, and under
  critical pressure only one call runs at a time. Work *queues* — it never fails
  because memory is tight.
* Live metrics (RAM, loaded models, queue depth, tokens/sec) are published as
  ``governor.metrics`` events and kept in a ring buffer for the Observatory.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal, NamedTuple

import psutil

from nexus.core.event_types import GovernorMetrics
from nexus.core.events import emit
from nexus.core.logging import get_logger

log = get_logger(__name__)

Pressure = Literal["normal", "elevated", "critical"]
GB = 1024**3


class MemorySample(NamedTuple):
    total: int
    available: int
    percent: float


def _psutil_probe() -> MemorySample:
    vm = psutil.virtual_memory()
    return MemorySample(vm.total, vm.available, vm.percent)


class ResourceGovernor:
    def __init__(
        self,
        configured_limit: int = 2,
        *,
        per_model_limit: int = 2,
        elevated_below_gb: float = 2.0,
        critical_below_gb: float = 1.0,
        memory_probe: Callable[[], MemorySample] = _psutil_probe,
        loaded_models: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None,
    ) -> None:
        self.configured_limit = configured_limit
        self.per_model_limit = per_model_limit
        self.elevated_below = elevated_below_gb * GB
        self.critical_below = critical_below_gb * GB
        self._probe = memory_probe
        self._loaded_models_fn = loaded_models
        self._cond = asyncio.Condition()
        self._in_flight = 0
        self._per_model: dict[str, int] = {}
        self._waiting = 0
        self._pressure: Pressure = "normal"
        self._memory = memory_probe()
        self._loaded: list[dict[str, Any]] = []
        self._tok_window: deque[tuple[float, int, float]] = deque()  # (ts, tokens, seconds)
        self.history: deque[dict[str, Any]] = deque(maxlen=900)  # ~30 min at 2 s
        self.paused = False

    # -- policy --------------------------------------------------------------------
    @property
    def pressure(self) -> Pressure:
        return self._pressure

    def _classify(self, sample: MemorySample) -> Pressure:
        if sample.available < self.critical_below:
            return "critical"
        if sample.available < self.elevated_below:
            return "elevated"
        return "normal"

    @property
    def limit(self) -> int:
        if self._pressure == "critical":
            return 1
        if self._pressure == "elevated":
            return max(1, self.configured_limit // 2)
        return self.configured_limit

    def set_limit(self, limit: int) -> None:
        self.configured_limit = max(1, limit)
        self._kick()

    def _kick(self) -> None:
        async def _notify() -> None:
            async with self._cond:
                self._cond.notify_all()

        with contextlib.suppress(RuntimeError):
            asyncio.get_running_loop().create_task(_notify())

    def _admissible(self, model: str) -> bool:
        if self.paused:
            return False
        if self._in_flight >= self.limit:
            return False
        return self._per_model.get(model, 0) < self.per_model_limit

    # -- admission -----------------------------------------------------------------
    @contextlib.asynccontextmanager
    async def slot(self, model: str) -> AsyncIterator[None]:
        """Hold one LLM-call slot for ``model``; waits (queues) while over the limit."""
        async with self._cond:
            self._waiting += 1
            try:
                await self._cond.wait_for(lambda: self._admissible(model))
            finally:
                self._waiting -= 1
            self._in_flight += 1
            self._per_model[model] = self._per_model.get(model, 0) + 1
        try:
            yield
        finally:
            async with self._cond:
                self._in_flight -= 1
                self._per_model[model] -= 1
                self._cond.notify_all()

    # -- telemetry -----------------------------------------------------------------
    def record_generation(self, tokens: int, seconds: float) -> None:
        now = time.monotonic()
        self._tok_window.append((now, tokens, seconds))
        while self._tok_window and now - self._tok_window[0][0] > 60:
            self._tok_window.popleft()

    @property
    def tokens_per_sec(self) -> float:
        toks = sum(t for _, t, _ in self._tok_window)
        secs = sum(s for _, _, s in self._tok_window)
        return round(toks / secs, 1) if secs > 0 else 0.0

    def metrics(self) -> GovernorMetrics:
        m = self._memory
        return GovernorMetrics(
            ram_total_gb=round(m.total / GB, 2),
            ram_available_gb=round(m.available / GB, 2),
            ram_percent=m.percent,
            pressure=self._pressure,
            limit=self.limit,
            configured_limit=self.configured_limit,
            in_flight=self._in_flight,
            queue_depth=self._waiting,
            tokens_per_sec=self.tokens_per_sec,
            loaded_models=self._loaded,
        )

    async def sample(self) -> GovernorMetrics:
        """Refresh memory + loaded models, re-evaluate the limit and publish metrics."""
        self._memory = self._probe()
        new = self._classify(self._memory)
        if new != self._pressure:
            log.warning("governor.pressure", old=self._pressure, new=new)
            self._pressure = new
            self._kick()
        if self._loaded_models_fn is not None:
            with contextlib.suppress(Exception):
                self._loaded = await self._loaded_models_fn()
        metrics = self.metrics()
        self.history.append({"ts": time.time(), **metrics.model_dump()})
        emit("governor.metrics", metrics)
        return metrics

    async def run(self, interval_s: float = 2.0) -> None:
        while True:
            try:
                await self.sample()
            except Exception as exc:  # noqa: BLE001 - telemetry must never take the app down
                log.error("governor.sample_failed", error=str(exc))
            await asyncio.sleep(interval_s)
