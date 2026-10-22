"""Flagship integration test (offline): chaos → Hawk → incident → tournament with
sandbox-grounded patches → approval → fix branch + hot reload → live verification
→ Fix Library. Uses a real demo-service subprocess and real sandboxed pytest runs;
only the LLM is scripted."""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from nexus.core.config import get_settings
from nexus.core.events import Event, bus
from nexus.core.runtime import runtime
from nexus.core.services import Services
from nexus.db import repo
from nexus.graph.schemas import ApprovalDecision
from nexus.llm.scripted import ScriptedLLM
from nexus.llm.types import LLMRequest
from nexus.playbooks.watcher import Watcher
from tests.fakes import line_of

BUGGY = 'email = order.get("email").strip().lower()'
FIXED = '    email = (order.get("email") or "").strip().lower()'

REPRO = """from app.orders import normalize_customer


def test_guest_order_without_email():
    assert normalize_customer({"email": None})["guest"] is True
"""


def solve(req: LLMRequest) -> str:
    line = 999 if req.agent_id == "frost" else line_of(req, BUGGY)  # c: out-of-range edit
    return json.dumps(
        {
            "rationale": "Guest orders have email=None; .strip() on None raises AttributeError.",
            "file": "app/orders.py",
            "start_line": line,
            "end_line": line,
            "replacement": FIXED,
        }
    )


def review(req: LLMRequest) -> str:
    labels = (
        req.messages[-1].content.split("Review exactly these labels: ")[-1].rstrip(".").split(", ")
    )
    return json.dumps(
        {
            "reviews": [
                {
                    "label": lab.strip(),
                    "correctness": 8,
                    "risk": 2,
                    "simplicity": 8,
                    "completeness": 8,
                    "reason": "Handles None.",
                }
                for lab in labels
            ]
        }
    )


def healing_llm() -> ScriptedLLM:
    return ScriptedLLM(
        {
            "rewrite": json.dumps(
                {"goal": "heal", "clarified_task": "Heal the demo-service incident."}
            ),
            "plan": "not a plan",  # → planner falls back to the playbook template (validated path)
            "react": json.dumps(
                {
                    "thought": "Looked at the evidence.",
                    "action": "final",
                    "action_input": {},
                    "final_answer": "normalize_customer crashes on guest orders (email None).",
                }
            ),
            "reproduce": json.dumps({"reasoning": "guest orders", "test_code": REPRO}),
            "solve": solve,
            "review": review,
            "debate": json.dumps({"decision": "defend", "rationale": "ok"}),
            "judge": json.dumps({"reasoning": "Both a and b pass every test; c did not apply."}),
            "summarise": "- summary",
        }
    )


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_DEMO_SERVICE_PORT", str(free_port()))
    monkeypatch.setenv("NEXUS_VERIFY_WINDOW_S", "2")
    monkeypatch.setenv("NEXUS_SMTP_PORT", "9")
    get_settings.cache_clear()


@pytest.fixture
def events() -> list[Event]:
    captured: list[Event] = []
    bus.reset()
    bus.add_listener(captured.append)
    return captured


@asynccontextmanager
async def live_demo(llm: ScriptedLLM) -> AsyncIterator[tuple[Services, Watcher]]:
    async with runtime(get_settings(), provider=llm, recover=False) as svc:
        await svc.demo.start()
        try:
            for _ in range(60):
                if (await svc.demo.health()).get("window"):
                    break
                await asyncio.sleep(0.25)
            yield svc, Watcher(svc.demo, svc.db, svc.runner, auto_heal=True)
        finally:
            await svc.demo.stop()


async def until(pred: Any, seconds: float = 30) -> None:
    for _ in range(int(seconds * 4)):
        if await pred():
            return
        await asyncio.sleep(0.25)
    raise AssertionError("condition not reached")


async def ring_and_detect(svc: Services, watcher: Watcher) -> str:
    await svc.demo.set_switch("null_handling", True)

    async def degraded() -> bool:
        return (await svc.demo.health())["status"] != "healthy"

    # the service restarts and needs live traffic to look degraded: slow CI runners take
    # longer (until() returns as soon as it holds, so this costs nothing when fast)
    await until(degraded, seconds=90)
    await watcher.tick()
    await watcher.tick()
    incident = await watcher.open_incident()
    assert incident is not None
    assert incident.mission_id
    return incident.mission_id


async def test_self_healing_end_to_end(events: list[Event]) -> None:
    async with live_demo(healing_llm()) as (svc, watcher):
        mid = await ring_and_detect(svc, watcher)
        await asyncio.wait_for(svc.runner.wait(mid), timeout=120)

        state = (await svc.runner.graph.aget_state(svc.runner.config(mid))).values
        inputs = state["inputs"]
        assert "AttributeError" in inputs["digest"]
        assert inputs["focus"]["file"] == "app/orders.py"
        assert BUGGY in inputs["focus"]["code"]
        assert inputs["suspects"][0] == "app/orders.py"
        assert inputs["repro"]["repro_test"]  # LLM repro test kept: it failed on buggy code
        tests = {sid: p["tests"] for sid, p in state["proposals"].items()}
        assert tests["blaze"]["ok"] and tests["volt"]["ok"]
        assert tests["frost"]["applied"] is False  # grounding rejected the bad patch
        assert state["verdict"]["winner"] in {"blaze", "volt"}
        assert state["risk"]["route"] in {"dry_run", "approve"}

        [pending] = await svc.approvals.list(mission_id=mid)
        assert pending.payload["action"]["kind"] == "apply_patch"
        await svc.approvals.decide(
            pending.id, ApprovalDecision(decision="approve", reason="looks right")
        )
        await asyncio.wait_for(svc.runner.wait(mid), timeout=120)

        row = await repo.get_mission(svc.db, mid)
        assert row is not None
        assert (row.status, row.outcome) == ("completed", "success"), row.error
        assert row.report is not None
        assert 'or "")' in row.report["diff"]
        assert '(order.get("email") or "")' in svc.demo.read("app/orders.py")
        assert await svc.demo.current_ref() == "main"  # verified fix promoted to main
        stats = await svc.memory.stats()
        assert stats["fix_library"] == 1
        kinds = {e.type for e in events if e.mission_id == mid}
        assert {
            "incident.detected",
            "sandbox.test_result",
            "council.verdict",
            "interrupt.raised",
            "interrupt.resolved",
            "memory.stored",
        } <= kinds | {e.type for e in events}


async def test_failed_verification_rolls_back(
    events: list[Event], monkeypatch: pytest.MonkeyPatch
) -> None:
    from nexus.graph.schemas import VerificationResult
    from nexus.playbooks import get_playbook

    playbook = get_playbook("self_healing")

    async def bad_verify(state: dict[str, Any]) -> VerificationResult:
        return VerificationResult(ok=False, summary="Errors continue after the fix")

    monkeypatch.setattr(playbook, "verify", bad_verify)
    async with live_demo(healing_llm()) as (svc, watcher):
        mid = await ring_and_detect(svc, watcher)
        await asyncio.wait_for(svc.runner.wait(mid), timeout=120)
        await svc.runner.graph.aupdate_state(svc.runner.config(mid), {"limits": {"verify": 1}})
        [pending] = await svc.approvals.list(mission_id=mid)
        await svc.approvals.decide(pending.id, ApprovalDecision(decision="approve"))
        await asyncio.wait_for(svc.runner.wait(mid), timeout=120)
        row = await repo.get_mission(svc.db, mid)
        assert row is not None
        assert row.outcome == "rolled_back"
        # the live service is back on the buggy main; the fix branch is gone
        assert 'order.get("email").strip()' in svc.demo.read("app/orders.py")
        assert await svc.demo.current_ref() == "main"
