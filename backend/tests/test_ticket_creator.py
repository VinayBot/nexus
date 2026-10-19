"""Create Ticket: routing, the full mission, the email, and the no-id fallback."""

from __future__ import annotations

import asyncio
import json

import pytest
from sqlalchemy import select

from nexus.core.config import get_settings
from nexus.core.runtime import runtime
from nexus.db import repo
from nexus.db.models import OutboxRow, TicketRow
from nexus.graph.nodes.understand import keyword_route
from nexus.llm.simulation import simulation_llm


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_SMTP_PORT", "9")
    monkeypatch.setenv("NEXUS_RESULT_EMAIL", "owner@example.com")
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("task", "playbook"),
    [
        ("cretae ticket for fixing bug in pipeline and also share email", "ticket_creator"),
        ("Create a support ticket for the checkout bug", "ticket_creator"),
        ("open an issue about slow inventory", "ticket_creator"),
        ("Write a blog post about ticket systems", "web_builder"),
        ("Solve ticket T-101", "ticket_solver"),
    ],
)
def test_ticket_routing(task: str, playbook: str) -> None:
    assert keyword_route(task) == playbook


async def _run(svc: object, task: str) -> str:
    row = await svc.runner.create(task)  # type: ignore[attr-defined]
    await asyncio.wait_for(svc.runner.wait(row.id), timeout=90)  # type: ignore[attr-defined]
    return str(row.id)


async def test_users_request_creates_a_ticket_and_emails_it_once() -> None:
    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        mid = await _run(svc, "cretae ticket for fixing bug in pipeline and also share email")
        await asyncio.gather(*svc.notifier._tasks)
        m = await repo.get_mission(svc.db, mid)
        assert m is not None and m.status == "completed" and m.outcome == "success", m and m.error
        report = m.report or {}
        assert report["ticket_id"] == "T-105"  # after the seeded T-101..T-104
        assert report["answer"].startswith("# T-105: Order pipeline rejects valid orders")
        assert report["emailed_to"] == "owner@example.com"
        async with svc.db.session() as s:
            ticket = await s.get(TicketRow, "T-105")
            mails = (await s.execute(select(OutboxRow))).scalars().all()
        assert ticket is not None and "Steps to reproduce" in ticket.body
        assert ticket.labels == ["bug", "pipeline"]
        subjects = [x.subject for x in mails if x.mission_id == mid]
        assert subjects == ["[NEXUS] New ticket T-105: Order pipeline rejects valid orders"]


async def test_solver_without_a_ticket_id_falls_back_to_creating_one() -> None:
    llm = simulation_llm()
    llm.on("route", json.dumps({"playbook": "ticket_solver", "reason": "mentions a ticket"}))
    async with runtime(get_settings(), provider=llm, recover=False) as svc:
        mid = await _run(svc, "the checkout keeps failing, please track this problem")
        m = await repo.get_mission(svc.db, mid)
        assert m is not None and m.playbook == "ticket_creator" and m.status == "completed"
