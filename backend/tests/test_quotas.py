"""Per-user mission rate and daily token quota, and the X-Request-ID header."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy import update

from nexus.api.app import create_app
from nexus.core.config import get_settings
from nexus.core.runtime import runtime
from nexus.core.services import Services
from nexus.db.models import MissionRow
from nexus.llm.simulation import simulation_llm

TASK = {"task": "What is a reducer?", "playbook": "council_qa"}


@asynccontextmanager
async def api() -> AsyncIterator[tuple[Services, httpx.AsyncClient]]:
    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            yield svc, client


async def test_mission_rate_limit_per_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_MISSIONS_PER_MINUTE", "2")
    get_settings.cache_clear()
    async with api() as (svc, client):
        first = await client.post("/api/v1/missions", json=TASK)
        assert first.status_code == 201
        assert first.json()["inputs"]["created_by"] == "owner"  # who started it
        assert (await client.post("/api/v1/missions", json=TASK)).status_code == 201
        blocked = await client.post("/api/v1/missions", json=TASK)
        assert blocked.status_code == 429
        assert "per minute" in blocked.json()["detail"]
        assert int(blocked.headers["Retry-After"]) >= 1
        await svc.runner.wait(first.json()["id"])


async def test_daily_token_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_DAILY_TOKEN_QUOTA", "1000")
    get_settings.cache_clear()
    async with api() as (svc, client):
        made = await client.post("/api/v1/missions", json=TASK)
        assert made.status_code == 201
        await svc.runner.wait(made.json()["id"])
        async with svc.db.session() as s:  # pretend it was an expensive mission
            await s.execute(update(MissionRow).values(tokens=1500))
        over = await client.post("/api/v1/missions", json=TASK)
        assert over.status_code == 429
        assert "Daily token quota" in over.json()["detail"]


async def test_request_id_is_echoed_or_generated() -> None:
    async with api() as (_, client):
        given = await client.get("/api/v1/health", headers={"X-Request-ID": "trace-123"})
        assert given.headers["X-Request-ID"] == "trace-123"
        made = await client.get("/api/v1/health")
        assert len(made.headers["X-Request-ID"]) == 32
        unsafe = await client.get("/api/v1/health", headers={"X-Request-ID": "bad id\r\n<x>"})
        assert unsafe.headers["X-Request-ID"] != "bad id\r\n<x>"
