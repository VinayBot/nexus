"""Migrations, persistent rate limits, server-side sign-out, security headers, error shape."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from nexus.api.app import create_app
from nexus.auth.ratelimit import RateLimiter
from nexus.core.config import get_settings
from nexus.core.runtime import runtime
from nexus.core.services import Services
from nexus.db.engine import Database
from nexus.db.models import Base
from nexus.llm.simulation import simulation_llm


@asynccontextmanager
async def api() -> AsyncIterator[tuple[Services, httpx.AsyncClient]]:
    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            yield svc, client


# --- migrations -----------------------------------------------------------------------------
async def test_migrations_build_exactly_the_model_schema(tmp_path: Path) -> None:
    db = Database(tmp_path / "m.db")
    await db.init()
    async with db.engine.connect() as conn:

        def diff(sync_conn: object) -> list[object]:
            ctx = MigrationContext.configure(sync_conn)  # type: ignore[arg-type]
            return list(compare_metadata(ctx, Base.metadata))

        assert await conn.run_sync(diff) == []  # no model change without a migration
        version = (await conn.execute(text("select version_num from alembic_version"))).scalar()
    await db.close()
    from nexus.db.migrate import SCRIPTS

    heads = sorted(p.name.split("_")[0] for p in (SCRIPTS / "versions").glob("0*.py"))
    assert version == heads[-1]


async def test_database_from_before_migrations_is_stamped_then_upgraded(tmp_path: Path) -> None:
    from nexus.db.migrate import BASELINE

    db = Database(tmp_path / "old.db")
    async with db.engine.begin() as conn:  # what create_all made in earlier versions
        await conn.run_sync(
            lambda c: Base.metadata.create_all(
                c,
                tables=[
                    t
                    for name, t in Base.metadata.tables.items()
                    if name not in {"rate_hits", "revoked_tokens"}
                ],
            )
        )
        await conn.execute(text("insert into users values ('kept', 'x', 'owner', 1.0)"))
    await db.init()
    async with db.engine.connect() as conn:
        tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
        kept = (await conn.execute(text("select username from users"))).scalar()
    await db.close()
    assert {"rate_hits", "revoked_tokens", "alembic_version"} <= tables
    assert kept == "kept"  # data survived
    assert BASELINE == "0001"


# --- rate limits in the database ------------------------------------------------------------
async def test_rate_limit_survives_a_restart() -> None:
    limiter = RateLimiter("t", limit=2, window_s=60)
    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        assert await limiter.allow(svc.db, "k", now=100.0)
        assert await limiter.allow(svc.db, "k", now=101.0)
    async with runtime(get_settings(), provider=simulation_llm(), recover=False) as svc:
        assert not await limiter.allow(svc.db, "k", now=102.0)  # still counted after restart
        assert await limiter.retry_after(svc.db, "k", now=102.0) == 59
        assert await limiter.allow(svc.db, "other", now=102.0)  # keys are independent
        assert await limiter.allow(svc.db, "k", now=161.0)  # the window slid past


# --- server-side sign-out -------------------------------------------------------------------
async def test_logout_revokes_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXUS_AUTH_ENABLED", "true")
    get_settings.cache_clear()
    async with api() as (_, client):
        creds = {"username": "vinay", "password": "s3cret-pass"}
        token = (await client.post("/api/v1/auth/setup", json=creds)).json()["token"]
        auth = {"Authorization": f"Bearer {token}"}
        assert (await client.get("/api/v1/auth/me", headers=auth)).status_code == 200
        assert (await client.post("/api/v1/auth/logout", headers=auth)).status_code == 204
        assert (await client.get("/api/v1/auth/me", headers=auth)).status_code == 401
        fresh = (await client.post("/api/v1/auth/login", json=creds)).json()["token"]
        again = {"Authorization": f"Bearer {fresh}"}
        assert (await client.get("/api/v1/auth/me", headers=again)).status_code == 200


# --- headers and errors ---------------------------------------------------------------------
async def test_security_headers() -> None:
    async with api() as (_, client):
        res = await client.get("/api/v1/health")
        assert res.headers["X-Content-Type-Options"] == "nosniff"
        assert res.headers["X-Frame-Options"] == "DENY"
        assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]
        site = await client.get("/sites/missing/")
        assert "script-src 'none'" in site.headers["Content-Security-Policy"]
        assert "X-Frame-Options" not in site.headers  # the app previews pages in a frame


async def test_errors_carry_the_request_id() -> None:
    async with api() as (_, client):
        missing = await client.get("/api/v1/missions/nope", headers={"X-Request-ID": "abc-1"})
        assert missing.status_code == 404
        assert missing.json()["request_id"] == "abc-1"
        assert missing.json()["detail"]
        bad = await client.post("/api/v1/missions", json={"task": "x"})
        assert bad.status_code == 422
        assert isinstance(bad.json()["detail"], list)
        assert bad.json()["request_id"] == bad.headers["X-Request-ID"]
