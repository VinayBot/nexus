from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nexus.api.app import create_app
from nexus.core.config import ModelProfile, get_settings


def test_health_is_ok() -> None:
    with TestClient(create_app()) as client:
        body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"


def test_ready_reports_ollama_down_but_sqlite_ok() -> None:
    with TestClient(create_app()) as client:
        body = client.get("/api/v1/health/ready").json()
    checks = {c["name"]: c["status"] for c in body["checks"]}
    store = "postgresql" if get_settings().uses_postgres else "sqlite"
    assert checks == {store: "ok", "ollama": "down"}
    assert body["status"] == "down"


def test_profile_defaults_and_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    assert get_settings().model_profile is ModelProfile.LITE
    monkeypatch.setenv("NEXUS_MODEL_PROFILE", "standard")
    monkeypatch.setenv("NEXUS_MODEL_FAST", "qwen3:4b")
    get_settings.cache_clear()
    models = get_settings().models
    assert models.main == "qwen2.5-coder:7b"
    assert models.fast == "qwen3:4b"


def test_large_json_responses_are_gzipped_small_ones_are_not() -> None:
    with TestClient(create_app()) as client:
        big = client.get("/api/v1/agents", headers={"Accept-Encoding": "gzip"})
        small = client.get("/api/v1/health", headers={"Accept-Encoding": "gzip"})
    assert big.headers.get("content-encoding") == "gzip"
    assert len(big.json()) == 14  # TestClient transparently decompresses
    assert "content-encoding" not in small.headers
