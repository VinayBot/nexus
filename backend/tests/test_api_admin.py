"""Owner and edge routes over HTTP: user management rules, uploads, chaos switches, the
guide's streamed answer, model profiles and the not-found paths."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest

from nexus.api.app import create_app
from nexus.core.config import get_settings
from nexus.core.runtime import runtime
from nexus.core.services import Services
from nexus.llm.simulation import simulation_llm


@asynccontextmanager
async def api() -> AsyncIterator[tuple[Services, httpx.AsyncClient]]:
    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            yield svc, client


async def test_user_management_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_AUTH_ENABLED", "true")
    get_settings.cache_clear()
    async with api() as (_, client):
        owner = (
            await client.post(
                "/api/v1/auth/setup", json={"username": "olga", "password": "pw-123456"}
            )
        ).json()["token"]
        h = {"Authorization": f"Bearer {owner}"}
        new = {"username": "bob", "password": "pw-123456", "role": "viewer"}
        assert (await client.post("/api/v1/auth/users", json=new, headers=h)).status_code == 201
        dup = await client.post("/api/v1/auth/users", json=new, headers=h)
        assert dup.status_code == 409
        role = await client.put("/api/v1/auth/users/bob", json={"role": "operator"}, headers=h)
        assert role.status_code == 200
        users = (await client.get("/api/v1/auth/users", headers=h)).json()
        assert {u["username"]: u["role"] for u in users} == {"olga": "owner", "bob": "operator"}
        last = await client.put("/api/v1/auth/users/olga", json={"role": "viewer"}, headers=h)
        assert last.status_code == 409  # NEXUS needs at least one owner
        assert (await client.delete("/api/v1/auth/users/olga", headers=h)).status_code == 409
        assert (await client.delete("/api/v1/auth/users/ghost", headers=h)).status_code == 404
        assert (
            await client.put("/api/v1/auth/users/ghost", json={"role": "viewer"}, headers=h)
        ).status_code == 404
        assert (await client.delete("/api/v1/auth/users/bob", headers=h)).status_code == 204
        audit = (await client.get("/api/v1/audit", headers=h)).json()
        actions = {a["action"] for a in audit}
        assert {"auth.user_created", "auth.role_changed", "auth.user_deleted"} <= actions
        assert (await client.post("/api/v1/auth/logout")).status_code == 401  # needs a session


async def test_uploads_are_parsed_and_limited() -> None:
    async with api() as (_, client):
        md = await client.post(
            "/api/v1/uploads/parse", files={"file": ("spec.md", b"# Books API\nTitle, author")}
        )
        assert md.status_code == 200 and md.json()["chars"] == 25
        exe = await client.post("/api/v1/uploads/parse", files={"file": ("x.exe", b"MZ")})
        assert exe.status_code == 415
        big = await client.post(
            "/api/v1/uploads/parse", files={"file": ("big.txt", b"x" * (2 * 1024 * 1024 + 10))}
        )
        assert big.status_code == 413


async def test_not_found_paths() -> None:
    async with api() as (_, client):
        for path in (
            "/api/v1/tickets/T-999/attachments/log.txt",
            "/api/v1/missions/nope/download",
            "/api/v1/missions/nope",
            "/api/v1/approvals/nope",
        ):
            assert (await client.get(path)).status_code == 404, path
        assert (
            await client.post("/api/v1/chaos/no-such-switch", json={"enabled": True})
        ).status_code == 404
        assert (await client.post("/api/v1/incidents/nope/heal")).status_code == 404
        assert (await client.post("/api/v1/dead-letters/12345/retry")).status_code == 404


async def test_ticket_attachment_round_trip() -> None:
    async with api() as (svc, client):
        tid = (
            await client.post("/api/v1/tickets", json={"title": "Crash", "body": "trace"})
        ).json()["id"]
        from nexus.db.models import TicketRow

        async with svc.db.session() as s:
            row = await s.get(TicketRow, tid)
            assert row is not None
            row.attachments = [{"name": "log.txt", "content": "Traceback ..."}]
        got = await client.get(f"/api/v1/tickets/{tid}/attachments/log.txt")
        assert got.json() == {"name": "log.txt", "content": "Traceback ..."}
        assert (await client.get(f"/api/v1/tickets/{tid}/attachments/other")).status_code == 404


async def test_chaos_switch_and_reset_are_audited() -> None:
    async with api() as (_, client):
        switches = (await client.get("/api/v1/chaos")).json()["switches"]
        first = switches[0]["id"]
        on = await client.post(f"/api/v1/chaos/{first}", json={"enabled": True})
        assert on.status_code == 200
        assert (await client.post("/api/v1/chaos/reset")).status_code == 200
        audit = (await client.get("/api/v1/audit")).json()
        assert any(a["action"] == "chaos.toggle" for a in audit)


async def test_guide_streams_an_answer_and_keeps_history() -> None:
    async with api() as (_, client):
        assert (await client.get("/api/v1/guide/suggestions")).json()
        res = await client.post("/api/v1/guide/chat", json={"question": "What can NEXUS do?"})
        assert res.status_code == 200
        assert "event: meta" in res.text
        cid = next(
            line.split('"conversation_id": "')[1].split('"')[0]
            for line in res.text.splitlines()
            if "conversation_id" in line
        )
        history = (await client.get(f"/api/v1/guide/history/{cid}")).json()
        assert [m["role"] for m in history][:2] == ["user", "assistant"]


async def test_model_profiles_are_described() -> None:
    async with api() as (_, client):
        info = (await client.get("/api/v1/models")).json()
        assert {p["id"] for p in info["profiles"]} >= {"lite", "balanced", "standard"}
        assert info["active"]
