"""Human-in-the-loop: approval interrupts, signed email links, time travel."""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, ClassVar

import pytest
from sqlalchemy import select

from nexus.core.config import get_settings
from nexus.core.events import Event, bus
from nexus.core.runtime import runtime
from nexus.core.services import Services
from nexus.db import repo
from nexus.db.models import ApprovalRow, AuditRow, OutboxRow
from nexus.graph.schemas import ApprovalDecision, ExecutionResult, ProposedAction
from nexus.hitl.tokens import TokenError, TokenService
from nexus.playbooks import _PLAYBOOKS, get_playbook, register
from nexus.playbooks.council_qa import CouncilQA
from tests.fakes import council_llm, local_toolbox


class RiskyQA(CouncilQA):
    """Council Q&A whose result is emailed — policy forces a human approval."""

    id = "risky_qa"
    executed: ClassVar[list[str]] = []

    def proposed_action(self, state: dict[str, Any]) -> ProposedAction:
        return ProposedAction(
            kind="send_email", summary="Email the answer to the team", blast_radius="external"
        )

    async def execute(self, state: dict[str, Any]) -> ExecutionResult:
        self.executed.append(state["mission_id"])
        return ExecutionResult(ok=True, summary="sent")


@pytest.fixture(autouse=True)
def setup(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("NEXUS_SMTP_PORT", "9")
    get_settings.cache_clear()
    get_playbook("council_qa")  # load built-ins
    register(RiskyQA())
    RiskyQA.executed = []
    yield
    _PLAYBOOKS.pop("risky_qa", None)


@pytest.fixture
def events() -> list[Event]:
    captured: list[Event] = []
    bus.reset()
    bus.add_listener(captured.append)
    return captured


@asynccontextmanager
async def rt() -> AsyncIterator[Services]:
    async with runtime(
        get_settings(), provider=council_llm(), toolbox=local_toolbox(), recover=False
    ) as svc:
        yield svc


async def finish(svc: Services, mid: str) -> None:
    await asyncio.wait_for(svc.runner.wait(mid), timeout=30)
    await bus.flush()


def links(html: str) -> dict[str, str]:
    found = re.findall(r'href="[^"]*/approvals/email/([^"]+)"[^>]*>(Approve|Reject)<', html)
    return {label.lower(): token for token, label in found}


async def test_approval_email_link_resumes_mission_and_is_single_use(events: list[Event]) -> None:
    async with rt() as svc:
        row = await svc.runner.create("What is a reducer?", playbook="risky_qa")
        await finish(svc, row.id)
        assert (await repo.get_mission(svc.db, row.id)).status == "paused"  # type: ignore[union-attr]
        [pending] = await svc.approvals.list(mission_id=row.id)
        assert pending.kind == "approve_action"
        assert pending.payload["risk"]["route"] in {"approve", "dry_run"}  # external email
        assert pending.email_status == "outbox"  # SMTP down in tests → kept in the outbox

        async with svc.db.session() as s:
            mail = (await s.execute(select(OutboxRow))).scalars().one()
        tokens = links(mail.html)
        assert set(tokens) == {"approve", "reject"}

        ea = svc.email_approvals
        code, page = await ea.confirm_page(tokens["approve"])
        assert code == 200
        assert "Confirm: Approve" in page
        assert RiskyQA.executed == []  # GET never decides

        code, page = await ea.decide(tokens["approve"])
        assert code == 200
        await finish(svc, row.id)
        done = await repo.get_mission(svc.db, row.id)
        assert done is not None
        assert (done.status, done.outcome) == ("completed", "success")
        assert RiskyQA.executed == [row.id]

        code, _ = await ea.decide(tokens["approve"])
        assert code == 400  # single use
        code, _ = await ea.decide(tokens["reject"])
        assert code == 409  # already decided
        async with svc.db.session() as s:
            audit = (await s.execute(select(AuditRow))).scalars().all()
        assert [(a.action, a.channel) for a in audit] == [("approval.approve", "email")]
        resolved = [e for e in events if e.type == "interrupt.resolved"]
        assert resolved[0].payload["channel"] == "email"


async def test_reject_from_ui_skips_execution() -> None:
    async with rt() as svc:
        row = await svc.runner.create("What is a reducer?", playbook="risky_qa")
        await finish(svc, row.id)
        [pending] = await svc.approvals.list(mission_id=row.id)
        await svc.approvals.decide(
            pending.id, ApprovalDecision(decision="reject", reason="not now")
        )
        await finish(svc, row.id)
        done = await repo.get_mission(svc.db, row.id)
        assert done is not None
        assert done.outcome == "rejected"
        assert RiskyQA.executed == []


async def test_critical_actions_need_explicit_override() -> None:
    async with rt() as svc:
        row = await svc.runner.create("What is a reducer?", playbook="risky_qa")
        await finish(svc, row.id)
        [pending] = await svc.approvals.list(mission_id=row.id)
        async with svc.db.session() as s:
            r = await s.get(ApprovalRow, pending.id)
            assert r is not None
            r.payload = {**r.payload, "requires_override": True}
        with pytest.raises(Exception, match="override"):
            await svc.approvals.decide(pending.id, ApprovalDecision(decision="approve"))
        await svc.approvals.decide(
            pending.id, ApprovalDecision(decision="approve", reason="override: tested by hand")
        )
        await finish(svc, row.id)
        assert RiskyQA.executed == [row.id]


async def test_tampered_and_expired_tokens_are_rejected() -> None:
    async with rt() as svc:
        ts = TokenService("secret", svc.db)
        good = ts.issue("a1", "approve")
        assert ts.verify(good).approval_id == "a1"
        with pytest.raises(TokenError, match="invalid"):
            ts.verify(good[:-2] + ("aa" if not good.endswith("aa") else "bb"))
        with pytest.raises(TokenError, match="invalid"):
            TokenService("other-secret", svc.db).verify(good)
        expired = TokenService("secret", svc.db, max_age_s=-1)
        with pytest.raises(TokenError, match="expired"):
            expired.verify(good)


async def test_time_travel_runner_up_fork_and_compare(events: list[Event]) -> None:
    async with rt() as svc:
        row = await svc.runner.create("What is a reducer?", playbook="council_qa")
        await finish(svc, row.id)
        tt = svc.timetravel
        before = await tt.history(row.id)
        assert len(before["branches"]) == 1
        main_head = before["branches"][0]["head"]
        original = (await svc.runner.graph.aget_state(svc.runner.config(row.id))).values

        fork = await tt.choose_runner_up(row.id)
        await finish(svc, row.id)
        after = await tt.history(row.id)
        labels = sorted(b["label"] for b in after["branches"])
        assert labels == ["main", f"runner-up {original['verdict']['runner_up']}"]
        fork_head = next(b["head"] for b in after["branches"] if b["label"] != "main")

        cmp = await tt.compare(row.id, main_head, fork_head)
        assert cmp["a"]["winner"] == original["verdict"]["winner"]
        assert cmp["b"]["winner"] == original["verdict"]["runner_up"]
        assert cmp["b"]["outcome"] == "success"
        assert cmp["fork_point"] is not None
        assert fork["checkpoint_id"] in cmp["b"]["lineage"]
        assert any(e.type == "timetravel.fork" for e in events)


async def test_fork_with_state_patch_reruns_from_checkpoint() -> None:
    async with rt() as svc:
        row = await svc.runner.create("What is a reducer?", playbook="council_qa")
        await finish(svc, row.id)
        history = await svc.timetravel.history(row.id)
        after_plan = next(c for c in history["checkpoints"] if c["writer"] == "plan")
        await svc.timetravel.fork(
            row.id, after_plan["checkpoint_id"], {"limits": {"react": 1}}, label="tight react"
        )
        await finish(svc, row.id)
        state = (await svc.runner.graph.aget_state(svc.runner.config(row.id))).values
        assert state["limits"]["react"] == 1
        assert state["outcome"] == "success"
        assert all(f["iterations"] <= 1 for f in state["findings"][-2:])
