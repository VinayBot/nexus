"""Shared fixtures: every test gets its own data directory and fresh settings."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from nexus.core.config import get_settings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("NEXUS_ENV", "test")
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path / "data"))
    # auth has its own tests (test_auth.py); the rest exercise features as the local owner
    monkeypatch.setenv("NEXUS_AUTH_ENABLED", "false")
    monkeypatch.setenv("NEXUS_OLLAMA_BASE_URL", "http://127.0.0.1:9")  # nothing listens here
    monkeypatch.setenv("NEXUS_DEMO_AUTOSTART", "false")
    monkeypatch.setenv("NEXUS_SANDBOX_BACKEND", "local")
    if pg := os.environ.get("NEXUS_TEST_DATABASE_URL"):  # the PostgreSQL CI job
        reset_postgres(pg)
        monkeypatch.setenv("NEXUS_DATABASE_URL", pg)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def reset_postgres(url: str) -> None:
    """Every test starts from an empty schema, like a fresh SQLite file."""
    import psycopg

    from nexus.db.checkpoints import psycopg_url

    with psycopg.connect(psycopg_url(url), autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
