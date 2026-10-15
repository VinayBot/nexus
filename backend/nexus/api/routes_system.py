"""Liveness, readiness and system-info endpoints."""

from __future__ import annotations

import sqlite3

import httpx
from fastapi import APIRouter

from nexus import __version__
from nexus.api.schemas import DependencyCheck, Liveness, ModelRoles, Readiness, SystemInfo
from nexus.core.config import Settings, get_settings

router = APIRouter(tags=["system"])


async def check_ollama(settings: Settings) -> DependencyCheck:
    """Ollama is reachable and every configured model is pulled."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        return DependencyCheck(name="ollama", status="down", detail=f"unreachable: {exc!s}")

    pulled = {m["name"] for m in resp.json().get("models", [])}
    pulled |= {name.removesuffix(":latest") for name in pulled}
    wanted = set(settings.models.model_dump().values())
    missing = sorted(wanted - pulled)
    if missing:
        return DependencyCheck(
            name="ollama", status="degraded", detail=f"missing models: {', '.join(missing)}"
        )
    return DependencyCheck(name="ollama", status="ok", detail="all configured models pulled")


def check_sqlite(settings: Settings) -> DependencyCheck:
    """The data directory is writable and SQLite opens."""
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(settings.sqlite_path) as conn:
            conn.execute("select 1")
    except (OSError, sqlite3.Error) as exc:
        return DependencyCheck(name="sqlite", status="down", detail=str(exc))
    return DependencyCheck(name="sqlite", status="ok", detail=str(settings.sqlite_path))


def worst(checks: list[DependencyCheck]) -> Readiness:
    order = {"ok": 0, "degraded": 1, "down": 2}
    status = max((c.status for c in checks), key=order.__getitem__, default="ok")
    return Readiness(status=status, checks=checks)


@router.get("/health", response_model=Liveness)
async def health() -> Liveness:
    """The process is up. Cheap; safe for frequent polling."""
    return Liveness(version=__version__)


@router.get("/health/ready", response_model=Readiness)
async def ready() -> Readiness:
    """Dependencies the backend needs to run missions."""
    settings = get_settings()
    return worst([check_sqlite(settings), await check_ollama(settings)])


@router.get("/system/info", response_model=SystemInfo)
async def system_info() -> SystemInfo:
    settings = get_settings()
    return SystemInfo(
        version=__version__,
        env=settings.env,
        model_profile=settings.model_profile.value,
        models=ModelRoles(**settings.models.model_dump()),
        num_ctx=settings.num_ctx,
        llm_max_concurrency=settings.llm_max_concurrency,
    )
