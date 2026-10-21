"""Graph behaviour with a deterministic fake LLM: routing, fan-out/fan-in, cycles and
their guards, interrupt/resume, and crash recovery from the SQLite checkpointer."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
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
from tests.fakes import council_llm, local_toolbox


@pytest.fixture
def events() -> list[Event]:
    captured: list[Event] = []
    bus.reset()
    bus.add_listener(captured.append)
    return captured


async def start(llm: ScriptedLLM, *, recover: bool = False) -> AsyncIterator[Services]:
    async with runtime(
        get_settings(), provider=llm, toolbox=local_toolbox(), recover=recover
    ) as svc:
        yield svc


async def run(svc: Services, task: str, **kw: Any) -> str:
    row = await svc.runner.create(task, **kw)
    await asyncio.wait_for(svc.runner.wait(row.id), timeout=30)
    return row.id


def types(events: list[Event], mission_id: str) -> list[str]:
    return [e.type for e in events if e.mission_id == mission_id]


async def test_council_qa_runs_end_to_end(events: list[Event]) -> None:
    async for svc in start(council_llm()):
        mid = await run(svc, "What is a LangGraph reducer?", playbook="council_qa")
        row = await repo.get_mission(svc.db, mid)
        assert row is not None
        assert (row.status, row.outcome) == ("completed", "success")
        assert row.report is not None
        assert "a reducer merges" in (row.report["answer"] or "")

        state = (await svc.runner.graph.aget_state(svc.runner.config(mid))).values
        # two parallel workers fanned in through the findings reducer
        assert len(state["findings"]) == 2
        assert set(state["step_results"]) == {"facts", "context"}
        # three proposals, each reviewed by the two other solvers plus the critic
        assert len(state["proposals"]) == 3
        assert all(len(c["reviews"]) == 3 for c in state["scores"].values())

        seen = types(events, mid)
        for t in [
            "mission.started",
            "plan.created",
            "send.fanout",
            "send.fanin",
            "agent.thinking",
            "agent.action",
            "tool.called",
            "tool.result",
            "council.masked",
            "council.verdict",
            "risk.scored",
            "checkpoint.saved",
            "mission.completed",
        ]:
            assert t in seen, t
        fanout = next(e for e in events if e.type == "send.fanout" and e.mission_id == mid)
        assert fanout.payload["count"] == 2
        merged = {e.payload["channel"] for e in events if e.type == "reducer.merged"}
        assert {"findings", "proposals", "scores", "evidence", "step_results"} <= merged
        risk = next(e for e in events if e.type == "risk.scored")
        assert risk.payload["route"] == "auto"  # answers are LOW risk → no approval

        # events are persisted with gap-free per-mission sequence numbers
        stored = await repo.events_after(svc.db, mid)
        seqs = [e["seq"] for e in stored]
        assert seqs == list(range(1, len(seqs) + 1))


async def test_router_picks_playbook_and_emits_edge(events: list[Event]) -> None:
    async for svc in start(council_llm()):
        mid = await run(svc, "Explain reducers please")
        state = (await svc.runner.graph.aget_state(svc.runner.config(mid))).values
        assert state["playbook"] == "council_qa"
        edges = [
            e.payload for e in events if e.type == "edge.taken" and e.payload["source"] == "route"
        ]
        assert edges == [{"source": "route", "target": "plan", "label": "council_qa"}]


async def test_vague_task_interrupts_for_clarification_then_resumes(events: list[Event]) -> None:
    vague = json.dumps(
        {"goal": "?", "clarified_task": "?", "is_vague": True, "question": "Which framework?"}
    )
    clear = json.dumps({"goal": "Explain reducers", "clarified_task": "Explain LangGraph reducers"})
    async for svc in start(council_llm(rewrite=[vague, clear])):
        mid = await run(svc, "explain the thing")
        row = await repo.get_mission(svc.db, mid)
        assert row is not None and row.status == "paused"
        pending = await svc.approvals.list(mission_id=mid)
        assert [p.kind for p in pending] == ["answer_question"]
        assert pending[0].payload["question"] == "Which framework?"

        await svc.approvals.decide(
            pending[0].id, ApprovalDecision(decision="respond", response="LangGraph reducers")
        )
        await asyncio.wait_for(svc.runner.wait(mid), timeout=30)
        row = await repo.get_mission(svc.db, mid)
        assert row is not None and row.status == "completed"
        state = (await svc.runner.graph.aget_state(svc.runner.config(mid))).values
        assert state["clarifications"] == ["LangGraph reducers"]
        assert "interrupt.resolved" in types(events, mid)


async def test_validation_failures_hit_fix_and_replan_guards(events: list[Event]) -> None:
    bad = json.dumps({"addresses_question": False, "problems": "off topic"})
    async for svc in start(council_llm(grade=bad)):
        mid = await run(
            svc, "What is a reducer?", playbook="council_qa", limits={"fix": 1, "replan": 1}
        )
        state = (await svc.runner.graph.aget_state(svc.runner.config(mid))).values
        assert state["outcome"] == "partial"
        # fix loop ran once per plan revision, then one replan, then gave up
        assert state["loops"]["replan"] == 1
        assert state["plan"]["revision"] == 1
        labels = [
            e.payload["label"]
            for e in events
            if e.type == "edge.taken" and e.payload["source"] == "validate"
        ]
        assert labels == ["fail → retry fix", "fail → replan", "fail → retry fix", "fail → give up"]


async def test_react_iteration_guard_forces_final(events: list[Event]) -> None:
    loop = json.dumps(
        {"thought": "again", "action": "knowledge.search", "action_input": {"query": "x"}}
    )

    def react(req: LLMRequest) -> str:
        if "used all your steps" in req.messages[-1].content:
            return json.dumps({"final_answer": "best effort"})
        return loop

    async for svc in start(council_llm(react=react)):
        mid = await run(svc, "What is a reducer?", playbook="council_qa", limits={"react": 2})
        state = (await svc.runner.graph.aget_state(svc.runner.config(mid))).values
        assert all(f["iterations"] == 2 for f in state["findings"])
        assert all(f["summary"] == "best effort" and not f["ok"] for f in state["findings"])


async def test_crashed_mission_resumes_from_sqlite_checkpoint(events: list[Event]) -> None:
    gate = asyncio.Event()
    entered = asyncio.Event()

    async def slow_solve(req: LLMRequest) -> str:  # pragma: no cover - replaced below
        raise AssertionError

    llm = council_llm()
    original = llm.chat

    async def chat(req: LLMRequest, on_token: Any = None) -> Any:
        if req.purpose == "solve" and not gate.is_set():
            entered.set()
            await asyncio.sleep(3600)  # "kill" happens while the council is thinking
        return await original(req, on_token)

    llm.chat = chat
    async for svc in start(llm):
        row = await svc.runner.create("What is a reducer?", playbook="council_qa")
        await asyncio.wait_for(entered.wait(), timeout=30)
        mid = row.id
    # runtime exited (backend stopped) mid-mission
    plan_calls = sum(1 for c in llm.calls if c.purpose == "plan")
    async with AwaitDbStatus(mid) as status:
        assert status == "running"

    gate.set()
    async for svc in start(llm, recover=True):
        await asyncio.wait_for(svc.runner.wait(mid), timeout=30)
        row2 = await repo.get_mission(svc.db, mid)
        assert row2 is not None and row2.status == "completed"
        # planning was not redone: the graph continued from the last checkpoint
        assert sum(1 for c in llm.calls if c.purpose == "plan") == plan_calls
        started = [e.payload for e in events if e.type == "mission.started" and e.mission_id == mid]
        assert started[-1] == {"resumed": True}


class AwaitDbStatus:
    def __init__(self, mission_id: str) -> None:
        self.mission_id = mission_id

    async def __aenter__(self) -> str:
        from nexus.db.engine import Database

        self.db = Database(get_settings().database_target, pooled=False)
        row = await repo.get_mission(self.db, self.mission_id)
        assert row is not None
        return row.status

    async def __aexit__(self, *exc: object) -> None:
        await self.db.close()
