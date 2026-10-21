"""Accounts and RBAC over real HTTP: setup, login, rate limit, the role matrix, WebSockets."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexus.api.app import create_app
from nexus.auth.policy import required_role
from nexus.auth.security import hash_password, needs_rehash, verify_password
from nexus.core.config import get_settings
from nexus.core.runtime import runtime
from nexus.core.services import Services
from nexus.llm.simulation import simulation_llm


@pytest.fixture(autouse=True)
def auth_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_AUTH_ENABLED", "true")
    monkeypatch.setenv("NEXUS_SMTP_PORT", "9")
    get_settings.cache_clear()


@asynccontextmanager
async def api() -> AsyncIterator[tuple[Services, httpx.AsyncClient]]:
    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            yield svc, client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_password_hashing_is_argon2id() -> None:
    stored = hash_password("correct horse battery")
    assert stored.startswith("$argon2id$")
    assert verify_password(stored, "correct horse battery")
    assert not verify_password(stored, "wrong password!")
    assert not needs_rehash(stored)


def test_policy_table() -> None:
    assert required_role("GET", "/api/v1/health") is None
    assert required_role("POST", "/api/v1/auth/login") is None
    assert required_role("GET", "/api/v1/approvals/email/abc.def") is None
    assert required_role("GET", "/api/v1/missions") == "viewer"
    assert required_role("POST", "/api/v1/notify/intent") == "viewer"
    assert required_role("POST", "/api/v1/missions") == "operator"
    assert required_role("POST", "/api/v1/approvals/x/decide") == "operator"
    assert required_role("PUT", "/api/v1/settings") == "owner"
    assert required_role("PUT", "/api/v1/models") == "owner"
    assert required_role("POST", "/api/v1/chaos/bad_config") == "owner"
    assert required_role("DELETE", "/api/v1/missions/abc") == "owner"
    assert required_role("GET", "/api/v1/auth/users") == "owner"


async def test_setup_login_roles_and_audit() -> None:
    async with api() as (svc, c):
        assert (await c.get("/api/v1/missions")).status_code == 401  # nothing without a session
        assert (await c.get("/api/v1/auth/status")).json() == {
            "auth_enabled": True,
            "setup_required": True,
        }
        owner = (
            await c.post(
                "/api/v1/auth/setup", json={"username": "vinay", "password": "s3cret-pass"}
            )
        ).json()
        assert owner["role"] == "owner"
        again = await c.post(
            "/api/v1/auth/setup", json={"username": "eve", "password": "s3cret-pass"}
        )
        assert again.status_code == 409  # setup only works once
        h_owner = bearer(owner["token"])
        for name, role in (("olivia", "operator"), ("victor", "viewer")):
            r = await c.post(
                "/api/v1/auth/users",
                json={"username": name, "password": "pass-1234", "role": role},
                headers=h_owner,
            )
            assert r.status_code == 201
        login = await c.post(
            "/api/v1/auth/login", json={"username": "olivia", "password": "pass-1234"}
        )
        h_op = bearer(login.json()["token"])
        h_view = bearer(
            (
                await c.post(
                    "/api/v1/auth/login", json={"username": "victor", "password": "pass-1234"}
                )
            ).json()["token"]
        )
        assert (await c.get("/api/v1/auth/me", headers=h_view)).json()["role"] == "viewer"

        # viewer: read only
        assert (await c.get("/api/v1/missions", headers=h_view)).status_code == 200
        denied = await c.post("/api/v1/missions", json={"task": "What is ReAct?"}, headers=h_view)
        assert denied.status_code == 403 and "operator" in denied.json()["detail"]
        # operator: runs missions and decides approvals, but cannot change settings
        m = await c.post(
            "/api/v1/missions",
            json={"task": "Write a blog post about agents as an HTML page"},
            headers=h_op,
        )
        assert m.status_code == 201
        mid = m.json()["id"]
        await asyncio.wait_for(svc.runner.wait(mid), timeout=60)
        [pending] = await svc.approvals.list(mission_id=mid)
        assert (
            await c.post(
                f"/api/v1/approvals/{pending.id}/decide",
                json={"decision": "approve"},
                headers=h_view,
            )
        ).status_code == 403
        ok = await c.post(
            f"/api/v1/approvals/{pending.id}/decide",
            json={"decision": "approve", "by": "spoofed"},
            headers=h_op,
        )
        assert (
            ok.status_code == 200 and ok.json()["decision"]["by"] == "olivia"
        )  # real user, not the client's claim
        assert (
            await c.put("/api/v1/settings", json={"auto_heal": False}, headers=h_op)
        ).status_code == 403
        assert (await c.delete(f"/api/v1/missions/{mid}", headers=h_op)).status_code == 403
        # owner: everything
        assert (
            await c.put("/api/v1/settings", json={"auto_heal": False}, headers=h_owner)
        ).status_code == 200
        await asyncio.wait_for(svc.runner.wait(mid), timeout=60)
        assert (await c.delete(f"/api/v1/missions/{mid}", headers=h_owner)).status_code == 204

        # a tampered token is rejected; a token in the URL is not accepted (it would leak
        # into logs and history): browsers use the HttpOnly cookie instead
        c.cookies.clear()
        assert (
            await c.get("/api/v1/missions", headers=bearer(owner["token"] + "x"))
        ).status_code == 401
        assert (await c.get(f"/api/v1/missions?token={owner['token']}")).status_code == 401
        # the last owner can never be removed or demoted
        assert (
            await c.put("/api/v1/auth/users/vinay", json={"role": "viewer"}, headers=h_owner)
        ).status_code == 409
        assert (await c.delete("/api/v1/auth/users/vinay", headers=h_owner)).status_code == 409
        # deleting an account ends its access at once (role read from the DB each request)
        assert (await c.delete("/api/v1/auth/users/victor", headers=h_owner)).status_code == 204
        assert (await c.get("/api/v1/missions", headers=h_view)).status_code == 401


async def test_login_is_rate_limited() -> None:
    async with api() as (_, c):
        await c.post("/api/v1/auth/setup", json={"username": "vinay", "password": "s3cret-pass"})
        codes = [
            (
                await c.post(
                    "/api/v1/auth/login", json={"username": "vinay", "password": "wrong-pass"}
                )
            ).status_code
            for _ in range(6)
        ]
        assert codes[:5] == [401] * 5 and codes[5] == 429
        blocked = await c.post(
            "/api/v1/auth/login", json={"username": "vinay", "password": "s3cret-pass"}
        )
        assert blocked.status_code == 429 and "Retry-After" in blocked.headers


async def test_websocket_needs_a_session() -> None:
    async with runtime(get_settings(), provider=simulation_llm(), recover=False):
        tc = TestClient(create_app())  # no `with`: the runtime above already provides services
        tc.post("/api/v1/auth/setup", json={"username": "vinay", "password": "s3cret-pass"})
        token = tc.post(
            "/api/v1/auth/login", json={"username": "vinay", "password": "s3cret-pass"}
        ).json()["token"]
        tc.cookies.clear()  # the login above left the session cookie in the client
        with (
            pytest.raises(WebSocketDisconnect) as closed,
            tc.websocket_connect("/ws/global") as ws,
        ):
            ws.receive_json()
        assert closed.value.code == 4401
        session = {"cookie": f"nexus_session={token}"}
        with (
            pytest.raises(WebSocketDisconnect) as foreign,
            tc.websocket_connect(
                "/ws/global", headers={**session, "origin": "https://evil.example"}
            ) as ws,
        ):
            ws.receive_json()
        assert foreign.value.code == 4403  # cross-site WebSocket hijacking is refused
        with tc.websocket_connect("/ws/global", headers=session) as ws:
            ws.send_text("ping")
            assert ws.receive_json()["type"] in {"pong", "governor.metrics", "service.health"}


async def test_weak_secret_is_replaced_by_a_strong_private_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXUS_SECRET_KEY", "change-me")
    get_settings.cache_clear()
    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        key = svc.settings.secret_key
        assert key != "change-me" and len(key) >= 48
        stored = svc.settings.data_dir / "secret.key"
        assert stored.read_text() == key and stored.stat().st_mode & 0o777 == 0o600
