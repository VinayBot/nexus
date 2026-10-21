"""Simulation mode (no Ollama) completes the code missions for real: the scripted model
only proposes the edit; the workspace, sandbox tests, approval and verification are real."""

from __future__ import annotations

import asyncio

import pytest

from nexus.core.config import get_settings
from nexus.core.runtime import runtime
from nexus.db import repo
from nexus.db.models import TicketRow
from nexus.graph.schemas import ApprovalDecision
from nexus.llm.simulation import simulation_llm
from nexus.llm.simulation_code import code_fix, shown_files
from nexus.llm.types import ChatMessage, LLMRequest
from tests.test_self_healing import env, events, live_demo, ring_and_detect  # noqa: F401


def solver_request(listing: str) -> LLMRequest:
    return LLMRequest(
        model="sim",
        messages=[ChatMessage.user(listing)],
        purpose="solve",
        json_schema={"properties": {"start_line": {"type": "integer"}}},
    )


def test_the_simulated_solver_reads_the_numbered_files() -> None:
    listing = (
        "File app/orders.py (line numbers on the left):\n```\n"
        "  6| def normalize_customer(order: dict) -> dict:\n"
        '  7|     email = order.get("email").strip().lower()\n```'
    )
    assert shown_files(solver_request(listing)) == {
        "app/orders.py": {
            6: "def normalize_customer(order: dict) -> dict:",
            7: '    email = order.get("email").strip().lower()',
        }
    }
    edit = code_fix(solver_request(listing))
    assert '"start_line": 7' in edit and '(order.get(\\"email\\") or \\"\\")' in edit
    unknown = code_fix(solver_request(listing.replace(".strip()", ".lstrip()")))
    assert "no scripted fix" in unknown  # honest: no change, validation will say so


@pytest.mark.parametrize("ticket", ["T-101", "T-103"])
async def test_simulation_solves_seeded_tickets_with_real_tests(ticket: str) -> None:
    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        row = await svc.runner.create(f"Solve ticket {ticket}", playbook="ticket_solver")
        await asyncio.wait_for(svc.runner.wait(row.id), timeout=120)
        state = (await svc.runner.graph.aget_state(svc.runner.config(row.id))).values
        assert state["inputs"]["acceptance_test"]  # it failed on the unchanged code
        assert any(p["tests"]["ok"] for p in state["proposals"].values())
        for _ in range(3):
            pending = await svc.approvals.list(mission_id=row.id)
            if not pending:
                break
            await svc.approvals.decide(pending[0].id, ApprovalDecision(decision="approve"))
            await asyncio.wait_for(svc.runner.wait(row.id), timeout=120)
        done = await repo.get_mission(svc.db, row.id)
        assert done is not None and (done.status, done.outcome) == ("completed", "success")
        async with svc.db.session() as s:
            closed = await s.get(TicketRow, ticket)
        assert closed is not None and closed.status == "closed"


async def test_simulation_self_heals_a_chaos_bug_on_the_live_service() -> None:
    async with live_demo(simulation_llm()) as (svc, watcher):
        mid = await ring_and_detect(svc, watcher)  # null_handling switched on
        await asyncio.wait_for(svc.runner.wait(mid), timeout=120)
        for _ in range(3):
            pending = await svc.approvals.list(mission_id=mid)
            if not pending:
                break
            await svc.approvals.decide(pending[0].id, ApprovalDecision(decision="approve"))
            await asyncio.wait_for(svc.runner.wait(mid), timeout=120)
        row = await repo.get_mission(svc.db, mid)
        assert row is not None
        assert (row.status, row.outcome) == ("completed", "success"), row.error
        assert '(order.get("email") or "")' in svc.demo.read("app/orders.py")
