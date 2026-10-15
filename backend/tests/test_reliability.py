from __future__ import annotations

import pytest

from nexus.core.events import Event, bus
from nexus.llm.provider import ProviderError
from nexus.reliability.circuit_breaker import CircuitBreaker, CircuitOpenError
from nexus.reliability.json_repair import JsonRepairError, extract_json
from nexus.reliability.retry import with_retries


@pytest.fixture
def events() -> list[Event]:
    captured: list[Event] = []
    bus.reset()
    bus.add_listener(captured.append)
    return captured


def state(cb: CircuitBreaker) -> str:
    return cb.state


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ('Sure! ```json\n{"a": [1, 2,]}\n``` hope that helps', {"a": [1, 2]}),
        ("Here: {'a': True, 'b': None}", {"a": True, "b": None}),
        ('{plan: "x", steps: 3}', {"plan": "x", "steps": 3}),
        ('Answer {"a": {"b": "c"', {"a": {"b": "c"}}),  # truncated output
        ('noise {"x": "has } brace"} tail', {"x": "has } brace"}),
    ],
)
def test_extract_json_repairs_common_model_mistakes(text: str, expected: object) -> None:
    assert extract_json(text) == expected


def test_extract_json_rejects_prose() -> None:
    with pytest.raises(JsonRepairError):
        extract_json("I could not decide.")


def test_circuit_breaker_opens_half_opens_and_closes(events: list[Event]) -> None:
    now = [0.0]
    cb = CircuitBreaker("model:x", threshold=2, cooldown_s=10, clock=lambda: now[0])
    cb.before_call()
    cb.on_failure()
    cb.before_call()
    cb.on_failure()
    assert cb.state == "open"
    with pytest.raises(CircuitOpenError):
        cb.before_call()
    now[0] = 11
    cb.before_call()  # trial allowed
    assert state(cb) == "half_open"
    with pytest.raises(CircuitOpenError):
        cb.before_call()  # only one trial at a time
    cb.on_success()
    assert state(cb) == "closed"
    states = [e.payload["state"] for e in events if e.type == "circuit.state"]
    assert states == ["open", "half_open", "closed"]


def test_half_open_failure_reopens() -> None:
    now = [0.0]
    cb = CircuitBreaker("k", threshold=1, cooldown_s=5, clock=lambda: now[0])
    cb.before_call()
    cb.on_failure()
    now[0] = 6
    cb.before_call()
    cb.on_failure()
    assert cb.state == "open"


async def test_retries_emit_events_then_succeed(events: list[Event]) -> None:
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ProviderError("boom", retryable=True)
        return "ok"

    assert await with_retries(flaky, key="model:x", initial_s=0.001, max_s=0.002) == "ok"
    retries = [e for e in events if e.type == "retry"]
    assert [e.payload["attempt"] for e in retries] == [2, 3]
    assert all(e.payload["layer"] == "transport" for e in retries)


async def test_non_retryable_errors_fail_immediately() -> None:
    calls = 0

    async def bad() -> str:
        nonlocal calls
        calls += 1
        raise ProviderError("404 model not found", retryable=False)

    with pytest.raises(ProviderError):
        await with_retries(bad, key="k", initial_s=0.001)
    assert calls == 1
