"""The HTTP API end to end: every route group answers with the documented shape after a
real (scripted) mission has run. Complements the feature tests, which call services."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from nexus.api.app import create_app
from nexus.core.config import get_settings
from nexus.core.runtime import runtime
from nexus.core.services import Services
from nexus.llm.simulation import simulation_llm

TASK = {"task": "What is the difference between ReAct and Plan-and-Execute?"}


@pytest.fixture(autouse=True)
def quiet_mail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_SMTP_PORT", "9")  # nothing listens: emails go to the outbox
    get_settings.cache_clear()


@asynccontextmanager
async def api_with_mission() -> AsyncIterator[tuple[Services, httpx.AsyncClient, str]]:
    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            made = await client.post("/api/v1/missions", json={**TASK, "playbook": "council_qa"})
            assert made.status_code == 201
            mid = made.json()["id"]
            await asyncio.wait_for(svc.runner.wait(mid), timeout=60)
            yield svc, client, mid


async def ok(client: httpx.AsyncClient, method: str, path: str, **kw: object) -> object:
    res = await client.request(method, f"/api/v1{path}", **kw)  # type: ignore[arg-type]
    assert res.status_code < 300, f"{method} {path} → {res.status_code}: {res.text[:300]}"
    return res.json() if res.content else None


async def test_missions_events_state_and_report() -> None:
    async with api_with_mission() as (_, client, mid):
        listed = await ok(client, "GET", "/missions")
        assert isinstance(listed, list) and listed[0]["id"] == mid
        row = await ok(client, "GET", f"/missions/{mid}")
        assert isinstance(row, dict) and row["status"] == "completed"
        events = await ok(client, "GET", f"/missions/{mid}/events", params={"after_seq": 0})
        assert isinstance(events, list) and events[0]["seq"] == 1
        assert {"id", "type", "payload", "ts"} <= set(events[0])
        state = await ok(client, "GET", f"/missions/{mid}/state")
        assert isinstance(state, dict) and state["next"] == [] and state["tokens"]["calls"] > 0
        report = await ok(client, "GET", f"/missions/{mid}/report")
        assert isinstance(report, dict) and report["answer"]
        assert (await client.get("/api/v1/missions/nope/report")).status_code == 404


async def test_time_travel_history_compare_and_fork() -> None:
    async with api_with_mission() as (svc, client, mid):
        history = await ok(client, "GET", f"/missions/{mid}/history")
        assert isinstance(history, dict)
        points = history["checkpoints"]
        assert len(points) > 3
        first, last = points[0]["checkpoint_id"], points[-1]["checkpoint_id"]  # oldest first
        snap = await ok(client, "GET", f"/missions/{mid}/checkpoints/{first}")
        assert isinstance(snap, dict) and "values" in snap
        diff = await ok(client, "GET", f"/missions/{mid}/compare", params={"a": first, "b": last})
        assert isinstance(diff, dict)
        missing = await client.get(f"/api/v1/missions/{mid}/checkpoints/not-a-checkpoint")
        assert missing.status_code == 404
        plan_point = next(p for p in points if p.get("next") == ["assemble"])  # after planning
        forked = await ok(
            client,
            "POST",
            f"/missions/{mid}/fork",
            json={"checkpoint_id": plan_point["checkpoint_id"], "label": "again", "run": True},
        )
        assert isinstance(forked, dict) and forked["branch_id"] and forked["label"] == "again"
        await asyncio.wait_for(svc.runner.wait(mid), timeout=60)  # the branch re-runs
        after = await ok(client, "GET", f"/missions/{mid}/history")
        assert isinstance(after, dict)
        assert any(b["label"] == "again" for b in after["branches"])


async def test_audit_outbox_dead_letters_and_policies() -> None:
    async with api_with_mission() as (_, client, mid):
        audit = await ok(client, "GET", "/audit", params={"limit": 50})
        assert isinstance(audit, list)
        assert isinstance(await ok(client, "GET", "/outbox"), list)
        assert await ok(client, "GET", "/dead-letters") == []
        policies = await ok(client, "GET", "/policies")
        assert isinstance(policies, list) and {"id", "kind", "enabled"} <= set(policies[0])
        assert isinstance(await ok(client, "GET", "/approvals", params={"mission_id": mid}), list)


async def test_observability_evals_and_lab() -> None:
    from nexus.core.tracing import flush_tracing

    async with api_with_mission() as (_, client, mid):
        await asyncio.to_thread(flush_tracing)  # spans are written in batches
        traces = await ok(client, "GET", "/observability/traces", params={"mission_id": mid})
        assert isinstance(traces, list) and traces
        summary = await ok(client, "GET", "/observability/summary")
        assert isinstance(summary, dict) and summary
        assert isinstance(await ok(client, "GET", "/observability/logs"), list)
        suites = await ok(client, "GET", "/evals/suites")
        assert isinstance(suites, list) and suites
        assert isinstance(await ok(client, "GET", "/evals/runs"), list)
        assert isinstance(await ok(client, "GET", "/lab/tasks"), list)
        assert (await client.post("/api/v1/evals/no-such-suite/run")).status_code == 404
        evidence = await ok(client, "GET", "/curriculum/evidence")
        assert isinstance(evidence, dict) and evidence


async def test_settings_round_trip() -> None:
    async with api_with_mission() as (svc, client, _):
        before = await ok(client, "GET", "/settings")
        assert isinstance(before, dict)
        after = await ok(client, "PUT", "/settings", json={"pruning_strategy": "sliding_window"})
        assert isinstance(after, dict)
        assert svc.settings.pruning_strategy == "sliding_window"
        bad = await client.put("/api/v1/settings", json={"pruning_strategy": "nonsense"})
        assert bad.status_code == 422


async def test_memory_mcp_and_graph() -> None:
    async with api_with_mission() as (_, client, _):
        assert isinstance(await ok(client, "GET", "/memory/stats"), dict)
        hits = await ok(client, "GET", "/memory/search", params={"q": "reducer", "k": 3})
        assert isinstance(hits, list)
        assert isinstance(await ok(client, "GET", "/memory/collections/missions"), dict | list)
        assert isinstance(await ok(client, "GET", "/memory/map"), dict | list)
        servers = await ok(client, "GET", "/mcp/servers")
        assert isinstance(servers, dict | list) and servers
        assert isinstance(await ok(client, "GET", "/mcp/calls"), list)
        assert isinstance(await ok(client, "GET", "/mcp/sandbox"), dict)
        listed = await ok(client, "POST", "/mcp/try", json={"tool": "tickets.list_tickets"})
        assert isinstance(listed, dict)
        graph = await ok(client, "GET", "/graph/structure")
        assert isinstance(graph, dict) and graph
        playbooks = await ok(client, "GET", "/playbooks")
        assert isinstance(playbooks, list) and playbooks


async def test_tickets_agents_and_reputation() -> None:
    async with api_with_mission() as (_, client, _):
        made = await ok(
            client, "POST", "/tickets", json={"title": "Slow checkout", "body": "Steps: pay"}
        )
        assert isinstance(made, dict)
        tickets = await ok(client, "GET", "/tickets")
        assert isinstance(tickets, list) and any(t["title"] == "Slow checkout" for t in tickets)
        agents = await ok(client, "GET", "/agents")
        assert isinstance(agents, list) and len(agents) == 14
        echo = next(a for a in agents if a["id"] == "echo")
        updated = await ok(client, "PUT", "/agents/echo", json={**echo, "temperature": 0.3})
        assert isinstance(updated, dict) and updated["temperature"] == 0.3
        assert isinstance(await ok(client, "GET", "/reputation"), dict | list)
        reply = await ok(client, "POST", "/agents/echo/playground", json={"message": "hi"})
        assert isinstance(reply, dict)


async def test_system_governor_chaos_and_metrics() -> None:
    async with api_with_mission() as (_, client, _):
        info = await ok(client, "GET", "/system/info")
        assert isinstance(info, dict) and info["version"]
        assert isinstance(await ok(client, "GET", "/governor/metrics"), dict)
        assert isinstance(await ok(client, "GET", "/governor/history"), list)
        assert isinstance(await ok(client, "GET", "/governor/circuits"), list | dict)
        chaos = await ok(client, "GET", "/chaos")
        assert isinstance(chaos, dict | list)
        assert isinstance(await ok(client, "GET", "/incidents"), list)
        metrics = await client.get("/metrics")
        assert metrics.status_code == 200
        text = metrics.text
        assert "nexus_missions_total" in text or "nexus_missions" in text
        assert "# TYPE" in text


async def test_notify_preferences_and_intent() -> None:
    async with api_with_mission() as (_, client, _):
        status = await ok(client, "GET", "/notify")
        assert isinstance(status, dict) and "delivery" in status
        saved = await ok(client, "PUT", "/notify", json={"to": "lead@example.com", "enabled": True})
        assert isinstance(saved, dict) and saved["to"] == "lead@example.com"
        intent = await ok(
            client,
            "POST",
            "/notify/intent",
            json={"task": "Write a haiku and send the output to lead@example.com"},
        )
        assert isinstance(intent, dict) and intent["to"] == ["lead@example.com"]
        no_client = await client.get("/api/v1/notify/google/start")
        assert no_client.status_code == 422  # no Google client configured
        assert "secret" not in str(status).lower() or "client_secret" not in str(status)
