"""Shared fixtures: every test gets its own data directory and fresh settings."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from nexus.core.config import get_settings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("NEXUS_ENV", "test")
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("NEXUS_OLLAMA_BASE_URL", "http://127.0.0.1:9")  # nothing listens here
    monkeypatch.setenv("NEXUS_DEMO_AUTOSTART", "false")
    monkeypatch.setenv("NEXUS_SANDBOX_BACKEND", "local")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
