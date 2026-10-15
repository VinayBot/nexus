from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from nexus.core.config import ModelSet
from nexus.core.events import Event, bus
from nexus.core.governor import GB, MemorySample, ResourceGovernor
from nexus.llm.gateway import LLMGateway, LLMUnavailableError, StructuredOutputError
from nexus.llm.router import ModelRouter
from nexus.llm.scripted import ScriptedLLM
from nexus.llm.tokens import TokenBudget, calibration, estimate_messages, estimate_text
from nexus.llm.types import ChatMessage, LLMRequest
from nexus.reliability.circuit_breaker import BreakerRegistry

MODELS = ModelSet(main="big", fast="small", embed="emb")


class Verdict(BaseModel):
    winner: str
    confidence: float


@pytest.fixture
def events() -> list[Event]:
    captured: list[Event] = []
    bus.reset()
    bus.add_listener(captured.append)
    return captured


def gateway(llm: ScriptedLLM, *, fallback: str | None = None) -> LLMGateway:
    gov = ResourceGovernor(2, memory_probe=lambda: MemorySample(16 * GB, 8 * GB, 50.0))
    return LLMGateway(
        llm,
        ModelRouter(MODELS),
        gov,
        BreakerRegistry(),
        fallback_model=fallback,
        retry_initial_s=0.001,
    )


async def test_router_sends_cheap_purposes_to_fast_model(events: list[Event]) -> None:
    llm = ScriptedLLM(default="hi")
    gw = gateway(llm)
    await gw.complete([ChatMessage.user("x")], purpose="rewrite")
    await gw.complete([ChatMessage.user("x")], purpose="plan")
    assert [c.model for c in llm.calls] == ["small", "big"]
    routed = [e.payload["model"] for e in events if e.type == "llm.routed"]
    assert routed == ["small", "big"]


async def test_structured_reprompts_with_validation_error_then_escalates(
    events: list[Event],
) -> None:
    llm = ScriptedLLM().on(
        "grade",
        ["not json at all", '{"winner": "A"}', '{"winner": "B", "confidence": 0.8}'],
    )
    out = await gateway(llm).structured([ChatMessage.user("judge")], Verdict, purpose="grade")
    assert out == Verdict(winner="B", confidence=0.8)
    # two fast attempts failed validation, so the third went to the main model
    assert [c.model for c in llm.calls] == ["small", "small", "big"]
    # the re-prompt quotes the exact validation error
    assert "confidence: Field required" in llm.calls[2].messages[-1].content
    layers = [e.payload["layer"] for e in events if e.type == "retry"]
    assert layers == ["validation", "validation"]


async def test_structured_returns_safe_default_after_all_attempts() -> None:
    llm = ScriptedLLM().on("grade", "nope")
    default = Verdict(winner="none", confidence=0.0)
    gw = gateway(llm)
    out = await gw.structured([ChatMessage.user("x")], Verdict, purpose="grade", default=default)
    assert out is default
    with pytest.raises(StructuredOutputError):
        await gw.structured([ChatMessage.user("x")], Verdict, purpose="grade")


async def test_fallback_chain_alternate_model_then_reduced_context(events: list[Event]) -> None:
    def respond(req: LLMRequest) -> str:
        if req.model == "big":
            from nexus.llm.provider import ProviderError

            raise ProviderError("down", retryable=False)
        return f"from {req.model} with {len(req.messages)} msgs"

    llm = ScriptedLLM().on("plan", respond)
    out = await gateway(llm, fallback="small").complete(
        [ChatMessage.system("s")] + [ChatMessage.user(str(i)) for i in range(6)], purpose="plan"
    )
    assert out.content == "from small with 7 msgs"
    fallbacks = [e for e in events if e.type == "retry" and e.payload["layer"] == "fallback"]
    assert len(fallbacks) == 1


async def test_all_fallbacks_failing_raises_and_opens_circuit() -> None:
    llm = ScriptedLLM()
    llm.fail_next("plan", 100)
    gw = gateway(llm)
    for _ in range(3):  # threshold: 3 failed calls (retries inside one call count once)
        with pytest.raises(LLMUnavailableError):
            await gw.complete([ChatMessage.user("x")], purpose="plan")
    assert gw.breakers.get("model:big").state == "open"


async def test_streaming_emits_agent_token_events(events: list[Event]) -> None:
    llm = ScriptedLLM().on("solve", "thinking hard")
    await gateway(llm).complete([ChatMessage.user("x")], purpose="solve", agent_id="forge")
    tokens = [e for e in events if e.type == "agent.token"]
    assert tokens and tokens[0].payload == {
        "agent_id": "forge",
        "text": "thinking hard",
        "purpose": "solve",
    }
    call = next(e for e in events if e.type == "llm.call")
    assert call.payload["prompt_tokens"] > 0


def test_token_estimates_learn_from_real_counts() -> None:
    text = "x" * 360
    assert estimate_text(text, "m1") == 100
    for _ in range(30):
        calibration.observe("m1", 100, 150)
    assert 140 <= estimate_text(text, "m1") <= 151
    assert estimate_messages([ChatMessage.user(text)], "other") == 104


def test_budget_window_and_record() -> None:
    b = TokenBudget(num_ctx=4096, reserve_output=512)
    assert b.window == 3584 and b.fits(3584) and not b.fits(3585)
    b = b.record(1000, 200).record(500, 100)
    assert (b.total_prompt, b.total_completion, b.total) == (1500, 300, 1800)


async def test_governor_queues_instead_of_failing_under_memory_pressure() -> None:
    free: list[float] = [8 * GB]
    gov = ResourceGovernor(
        4, per_model_limit=4, memory_probe=lambda: MemorySample(16 * GB, int(free[0]), 50.0)
    )
    await gov.sample()
    assert gov.limit == 4
    free[0] = 0.5 * GB
    await gov.sample()
    assert gov.pressure == "critical" and gov.limit == 1

    running = 0
    peak = 0

    async def job() -> None:
        nonlocal running, peak
        async with gov.slot("m"):
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.01)
            running -= 1

    await asyncio.gather(*(job() for _ in range(5)))
    assert peak == 1  # all five completed, one at a time
    assert gov.metrics().queue_depth == 0


async def test_governor_per_model_limit() -> None:
    gov = ResourceGovernor(
        4, per_model_limit=1, memory_probe=lambda: MemorySample(16 * GB, 8 * GB, 50.0)
    )
    order: list[str] = []

    async def job(name: str) -> None:
        async with gov.slot("same"):
            order.append(f"start {name}")
            await asyncio.sleep(0.01)
            order.append(f"end {name}")

    await asyncio.gather(job("a"), job("b"))
    assert order == ["start a", "end a", "start b", "end b"]
