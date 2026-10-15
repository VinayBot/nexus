"""Ticket Solver, Project Builder and Dynamic Mission end-to-end (scripted LLM, real sandbox)."""

from __future__ import annotations

import asyncio
import json
import zipfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from nexus.core.config import get_settings
from nexus.core.events import Event, bus
from nexus.core.runtime import runtime
from nexus.core.services import Services
from nexus.db import repo
from nexus.db.models import TicketRow
from nexus.graph.schemas import ApprovalDecision
from nexus.llm.scripted import ScriptedLLM
from nexus.llm.types import LLMRequest
from nexus.playbooks import all_playbooks, reload_saved
from nexus.playbooks.dynamic import SavedPlaybookSpec, save_playbook
from tests.fakes import council_llm, line_of

FINAL = json.dumps(
    {"thought": "done", "action": "final", "action_input": {}, "final_answer": "Looked at it."}
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
                    "risk": 1,
                    "simplicity": 8,
                    "completeness": 8,
                    "reason": "ok",
                }
                for lab in labels
            ]
        }
    )


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_SMTP_PORT", "9")
    get_settings.cache_clear()


@pytest.fixture
def events() -> list[Event]:
    captured: list[Event] = []
    bus.reset()
    bus.add_listener(captured.append)
    return captured


@asynccontextmanager
async def rt(llm: ScriptedLLM) -> AsyncIterator[Services]:
    async with runtime(get_settings(), provider=llm, recover=False) as svc:
        yield svc


async def run_to_pause(svc: Services, task: str, **kw: object) -> str:
    row = await svc.runner.create(task, **kw)
    await asyncio.wait_for(svc.runner.wait(row.id), timeout=90)
    return row.id


async def approve_all(svc: Services, mid: str) -> None:
    for _ in range(3):
        pending = await svc.approvals.list(mission_id=mid)
        if not pending:
            return
        await svc.approvals.decide(pending[0].id, ApprovalDecision(decision="approve"))
        await asyncio.wait_for(svc.runner.wait(mid), timeout=90)


# --- Ticket Solver -----------------------------------------------------------------------
ACCEPT = """from app.orders import apply_discount


def test_welcome5_gives_five_percent():
    assert apply_discount(100.0, "welcome5") == 95.0
"""


def ticket_llm() -> ScriptedLLM:
    def solve(req: LLMRequest) -> str:
        line = line_of(req, "DISCOUNTS = {")
        return json.dumps(
            {
                "rationale": "Add the new code to the discount table.",
                "file": "app/config.py",
                "start_line": line,
                "end_line": line,
                "replacement": 'DISCOUNTS = {"SAVE10": 0.10, "VIP20": 0.20, "WELCOME5": 0.05}',
            }
        )

    return ScriptedLLM(
        {
            "rewrite": json.dumps({"goal": "solve T-101", "clarified_task": "Solve ticket T-101"}),
            "plan": "x",
            "plan:requirements": json.dumps(
                {
                    "summary": "Add WELCOME5 (5%)",
                    "acceptance_criteria": ["welcome5 gives 5% off"],
                    "likely_files": ["app/config.py"],
                    "acceptance_test": ACCEPT,
                }
            ),
            "react": FINAL,
            "solve": solve,
            "review": review,
            "judge": json.dumps({"reasoning": "All pass."}),
            "summarise": "-",
        }
    )


async def test_ticket_solver_attaches_evidence_after_approval(events: list[Event]) -> None:
    async with rt(ticket_llm()) as svc:
        mid = await run_to_pause(svc, "Please solve ticket T-101", playbook="ticket_solver")
        state = (await svc.runner.graph.aget_state(svc.runner.config(mid))).values
        assert state["inputs"]["acceptance_test"]  # failed on baseline → kept
        assert "app/config.py" in state["inputs"]["suspects"]
        assert all(p["tests"]["ok"] for p in state["proposals"].values())
        pending = await svc.approvals.list(mission_id=mid)
        assert pending[0].payload["action"]["kind"] == "comment_ticket"
        await approve_all(svc, mid)
        row = await repo.get_mission(svc.db, mid)
        assert row is not None
        assert (row.status, row.outcome) == ("completed", "success"), row.error
        async with svc.db.session() as s:
            t = await s.get(TicketRow, "T-101")
        assert t is not None
        assert t.status == "closed"
        assert {a["name"] for a in t.attachments} == {
            "test-report.txt",
            "fix.diff",
            "sandbox-output.txt",
        }
        assert "WELCOME5" in next(a for a in t.attachments if a["name"] == "fix.diff")["content"]


async def test_ticket_injection_is_flagged(events: list[Event]) -> None:
    async with rt(ticket_llm()) as svc:
        mid = await run_to_pause(svc, "Solve T-104", playbook="ticket_solver")
        state = (await svc.runner.graph.aget_state(svc.runner.config(mid))).values
        assert "ignore-instructions" in state["inputs"]["injection_flags"]
        assert any(
            e.type == "guardrail.triggered" and e.payload["kind"] == "injection" for e in events
        )


# --- Project Builder ------------------------------------------------------------------------
TEMPLATES = (
    Path(__file__).resolve().parents[1] / "nexus" / "playbooks" / "templates" / "fastapi_crud"
)


def builder_llm(break_first: bool = False) -> ScriptedLLM:
    spec = {
        "kind": "fastapi_crud",
        "name": "items",
        "entity": "Item",
        "fields": ["name: str", "price: float"],
        "files": [
            {"path": "app/models.py", "purpose": "models"},
            {"path": "app/store.py", "purpose": "storage", "depends_on": ["app/models.py"]},
            {"path": "app/main.py", "purpose": "api", "depends_on": ["app/store.py"]},
            {"path": "tests/test_api.py", "purpose": "tests", "depends_on": ["app/main.py"]},
        ],
    }
    state = {"broken": break_first}

    def code(req: LLMRequest) -> str:
        text = req.messages[-1].content
        path = (
            text.split("Write the complete content of ")[-1].split(".py")[0] + ".py"
            if "Write the complete content" in text
            else ""
        )
        if "tests fail" in text:  # repair: the broken file is the store
            return json.dumps(
                {"path": "app/store.py", "content": (TEMPLATES / "app/store.py").read_text()}
            )
        content = (TEMPLATES / path).read_text()
        if state["broken"] and path == "app/store.py":
            content = content.replace(
                "return self._items.get(item_id)", "return None"
            )  # GET returns 404 → tests fail
        return json.dumps({"content": content})

    return ScriptedLLM(
        {
            "rewrite": json.dumps({"goal": "build", "clarified_task": "Build an items API"}),
            "plan:spec": json.dumps(spec),
            "code": code,
            "summarise": "-",
        }
    )


async def test_project_builder_builds_tests_and_packages(events: list[Event]) -> None:
    async with rt(builder_llm()) as svc:
        mid = await run_to_pause(
            svc,
            "Build a small API to manage items with name and price.",
            playbook="project_builder",
        )
        state = (await svc.runner.graph.aget_state(svc.runner.config(mid))).values
        assert state["plan"]["source"] == "template"
        assert len(state["plan"]["steps"]) == 4
        assert state["validation"]["ok"], state["validation"]
        await approve_all(svc, mid)
        row = await repo.get_mission(svc.db, mid)
        assert row is not None
        assert row.outcome == "success", row.error
        assert row.report is not None
        assert row.report["download"].endswith("/download")
        with zipfile.ZipFile(svc.settings.data_dir / "exports" / f"{mid}.zip") as z:
            assert {"app/main.py", "tests/test_api.py"} <= set(z.namelist())
        fanouts = [
            e.payload["count"] for e in events if e.type == "send.fanout" and e.mission_id == mid
        ]
        assert fanouts == [1, 1, 1, 1]  # a dependency chain: one file per wave


async def test_project_builder_repairs_until_green() -> None:
    async with rt(builder_llm(break_first=True)) as svc:
        mid = await run_to_pause(svc, "Build an items API", playbook="project_builder")
        state = (await svc.runner.graph.aget_state(svc.runner.config(mid))).values
        assert state["loops"]["fix"] >= 1  # failed once, repaired, then passed
        assert state["validation"]["ok"]


# --- Dynamic + saved playbooks -----------------------------------------------------------------
async def test_dynamic_mission_requires_team_approval_then_saves_as_playbook(
    events: list[Event],
) -> None:
    llm = council_llm(
        route=json.dumps({"playbook": "dynamic", "reason": "custom"}),
        summarise="Reducers merge updates.",
    )
    async with rt(llm) as svc:
        mid = await run_to_pause(svc, "Write a short note on how our reducers work")
        pending = await svc.approvals.list(mission_id=mid)
        assert [p.kind for p in pending] == ["approve_team"]
        assert pending[0].payload["team"]["members"]
        assert not [
            e for e in events if e.type == "agent.thinking" and e.mission_id == mid
        ]  # nothing ran yet
        await approve_all(svc, mid)
        row = await repo.get_mission(svc.db, mid)
        assert row is not None
        assert row.outcome == "success"

        state = (await svc.runner.graph.aget_state(svc.runner.config(mid))).values
        save_playbook(
            svc.settings.data_dir / "playbooks",
            SavedPlaybookSpec(
                id="reducer_notes",
                title="Reducer notes",
                description="Explain reducers",
                plan=state["plan"],
            ),
        )
        reload_saved()
        assert "reducer_notes" in {p.id for p in all_playbooks()}
        mid2 = await run_to_pause(svc, "Explain reducers again", playbook="reducer_notes")
        row2 = await repo.get_mission(svc.db, mid2)
        assert row2 is not None
        assert row2.status == "completed"  # saved playbooks skip team approval
        state2 = (await svc.runner.graph.aget_state(svc.runner.config(mid2))).values
        assert [s["id"] for s in state2["plan"]["steps"]] == [
            s["id"] for s in state["plan"]["steps"]
        ]
