"""MCP servers through the real hub (in-memory MCP transport, full protocol)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from nexus.core.config import get_settings
from nexus.core.events import Event, MissionContext, bus, mission_context
from nexus.core.runtime import runtime
from nexus.core.services import Services
from nexus.db.models import OutboxRow, TicketRow
from nexus.llm.scripted import ScriptedLLM
from nexus.mcp_servers.hub import McpHub


@pytest.fixture
def events() -> list[Event]:
    captured: list[Event] = []
    bus.reset()
    bus.add_listener(captured.append)
    return captured


@pytest.fixture(autouse=True)
def mcp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_SANDBOX_BACKEND", "local")
    monkeypatch.setenv("NEXUS_SMTP_PORT", "9")  # nothing listens: mail goes to the outbox
    monkeypatch.setenv("NEXUS_DEMO_SERVICE_PORT", "9")
    get_settings.cache_clear()


@asynccontextmanager
async def mcp_runtime() -> AsyncIterator[Services]:
    """Opened inside each test: MCP clients must enter and exit in the same task."""
    async with runtime(get_settings(), provider=ScriptedLLM(), recover=False) as s:
        token = mission_context.set(MissionContext(mission_id="m1", thread_id="m1"))
        try:
            yield s
        finally:
            mission_context.reset(token)


def hub(svc: Services) -> McpHub:
    h: McpHub = svc.mcp
    return h


async def test_all_servers_and_hidden_params() -> None:
    async with mcp_runtime() as svc:
        h = hub(svc)
        assert set(h.clients) == {
            "workspace",
            "sandbox",
            "knowledge",
            "tickets",
            "notify",
            "observability",
            "demo",
        }
        specs = {s.name: s for s in h.specs(None)}
        assert "workspace.read_file" in specs
        assert "workspace" not in specs["workspace.read_file"].parameters["properties"]
        assert not any(n.startswith("notify.") for n in specs)  # system-only: never shown to agents
        health = await h.health()
        assert all(v["status"] == "ok" for v in health.values())


async def test_workspace_roundtrip_and_path_jail(events: list[Event]) -> None:
    async with mcp_runtime() as svc:
        h = hub(svc)
        w = await h.call(
            "workspace.write_file",
            {"path": "app/x.py", "content": "print(1)\n"},
            agent_id="forge",
            allowlist=None,
        )
        assert w.ok
        assert (svc.workspaces.path_for("m1") / "app" / "x.py").read_text() == "print(1)\n"
        r = await h.call(
            "workspace.read_file", {"path": "app/x.py"}, agent_id="forge", allowlist=None
        )
        assert "1| print(1)" in r.text
        bad = await h.call(
            "workspace.read_file", {"path": "../../../etc/passwd"}, agent_id="forge", allowlist=None
        )
        assert not bad.ok
        assert any(
            e.type == "guardrail.triggered" and e.payload["kind"] == "path_jail" for e in events
        )
        assert [e.type for e in events if e.type.startswith("tool.")][:2] == [
            "tool.called",
            "tool.result",
        ]


async def test_allowlist_and_system_only_notify() -> None:
    async with mcp_runtime() as svc:
        h = hub(svc)
        blocked = await h.call(
            "workspace.write_file",
            {"path": "a", "content": "b"},
            agent_id="echo",
            allowlist=["knowledge.search"],
        )
        assert not blocked.ok
        assert "allowlist" in blocked.text
        agent_mail = await h.call(
            "notify.send_email",
            {"to": "a@b.c", "subject": "s", "html": "h"},
            agent_id="swift",
            allowlist=None,
        )
        assert not agent_mail.ok
        assert "approval" in agent_mail.text
        sent = await h.call_system(
            "notify.send_email", {"to": "owner@nexus.local", "subject": "hi", "html": "<b>x</b>"}
        )
        assert sent.ok
        assert sent.data is not None
        assert sent.data["status"] == "outbox"
        async with svc.db.session() as s:
            assert await s.get(OutboxRow, sent.data["message_id"]) is not None


async def test_sandbox_runs_pytest_on_a_copy() -> None:
    async with mcp_runtime() as svc:
        root = svc.workspaces.ensure("m1")
        (root / "tests").mkdir()
        (root / "tests" / "test_a.py").write_text(
            "def test_ok():\n    assert 1\n\ndef test_bad():\n    assert 0\n"
        )
        out = await hub(svc).call(
            "sandbox.run_tests", {"target": "tests"}, agent_id="aegis", allowlist=None
        )
        assert out.data is not None
        assert (out.data["passed"], out.data["failed"]) == (1, 1)
        assert out.data["backend"] == "local (not isolated)"
        assert not (root / ".junit.xml").exists()  # the real workspace was not touched
        cmd = await hub(svc).call(
            "sandbox.run_command", {"command": "rm -rf /"}, agent_id="aegis", allowlist=None
        )
        assert cmd.data is not None
        assert "not allowed" in cmd.data["summary"]


async def test_knowledge_search() -> None:
    async with mcp_runtime() as svc:
        await svc.memory.add(
            "docs", "Reducers merge concurrent state updates in LangGraph.", {"title": "Reducers"}
        )
        out = await hub(svc).call(
            "knowledge.search",
            {"query": "reducers merge concurrent updates"},
            agent_id="echo",
            allowlist=None,
        )
        assert "Reducers" in out.text


async def test_tickets_local() -> None:
    async with mcp_runtime() as svc:
        async with svc.db.session() as s:
            s.add(
                TicketRow(
                    id="T-1",
                    title="Total is wrong",
                    body="Orders with 3 items...",
                    labels=["bug"],
                    comments=[],
                    attachments=[],
                )
            )
        h = hub(svc)
        got = await h.call("tickets.get", {"ticket_id": "T-1"}, agent_id="echo", allowlist=None)
        assert got.data is not None
        assert got.data["title"] == "Total is wrong"
        await h.call_system("tickets.comment", {"ticket_id": "T-1", "body": "Fixed in sandbox."})
        await h.call_system(
            "tickets.attach", {"ticket_id": "T-1", "name": "report.txt", "content": "3 passed"}
        )
        async with svc.db.session() as s:
            t = await s.get(TicketRow, "T-1")
            assert t is not None
            assert [c["body"] for c in t.comments] == ["Fixed in sandbox."]
            assert t.attachments[0]["name"] == "report.txt"


async def test_observability_reports_down_service() -> None:
    async with mcp_runtime() as svc:
        out = await hub(svc).call("observability.health", {}, agent_id="hawk", allowlist=None)
        assert out.data is not None
        assert out.data["status"] == "down"
