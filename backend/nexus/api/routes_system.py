"""Liveness, readiness and system-info endpoints."""

from __future__ import annotations

import sqlite3

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nexus import __version__
from nexus.api.schemas import DependencyCheck, Liveness, ModelRoles, Readiness, SystemInfo
from nexus.core.config import ModelProfile, ModelSet, Settings, get_settings
from nexus.core.services import services
from nexus.llm import profiles

router = APIRouter(tags=["system"])


def active_models(settings: Settings) -> ModelSet:
    try:
        return services().llm.router.models
    except RuntimeError:  # services not built (e.g. a bare health probe)
        return settings.models


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
    wanted = {m for m in active_models(settings).model_dump().values() if m}
    missing = sorted(wanted - pulled)
    if missing:
        return DependencyCheck(
            name="ollama", status="degraded", detail=f"missing models: {', '.join(missing)}"
        )
    return DependencyCheck(name="ollama", status="ok", detail="all configured models pulled")


async def check_database(settings: Settings) -> DependencyCheck:
    """SQLite: the data directory is writable and the file opens. PostgreSQL: it answers."""
    if settings.uses_postgres:
        from nexus.core.services import services

        try:
            await services().db.ping()
        except Exception as exc:  # any driver error means the store is down
            return DependencyCheck(name="postgresql", status="down", detail=type(exc).__name__)
        return DependencyCheck(name="postgresql", status="ok", detail="connected")
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
    if settings.llm_provider == "simulation":
        sim = DependencyCheck(name="ollama", status="ok", detail="simulation mode: scripted model")
        return worst([await check_database(settings), sim])
    return worst([await check_database(settings), await check_ollama(settings)])


@router.get("/system/info", response_model=SystemInfo)
async def system_info() -> SystemInfo:
    settings = get_settings()
    return SystemInfo(
        version=__version__,
        env=settings.env,
        model_profile=_active_profile(settings),
        models=ModelRoles(**active_models(settings).model_dump()),
        num_ctx=settings.num_ctx,
        llm_max_concurrency=settings.llm_max_concurrency,
        simulation=settings.llm_provider == "simulation",
    )


def _active_profile(settings: Settings) -> str:
    try:
        return str(services().extras.get("model_profile", settings.model_profile.value))
    except RuntimeError:
        return settings.model_profile.value


class ProfileChoice(BaseModel):
    profile: ModelProfile


@router.get("/models")
async def models() -> dict[str, object]:
    """Model profiles, which models each needs, and what Ollama has installed."""
    return await profiles.describe(services())


@router.put("/models")
async def choose_profile(body: ProfileChoice) -> dict[str, object]:
    svc = services()
    info = await profiles.describe(svc)
    chosen = next(p for p in info["profiles"] if p["id"] == body.profile.value)
    if chosen["missing"]:
        raise HTTPException(409, "not installed yet: use Install and switch")
    await profiles.apply(svc, body.profile)
    return await profiles.describe(svc)


@router.post("/models/install")
async def install_profile(body: ProfileChoice) -> dict[str, object]:
    """Download the profile's missing models in the background, then switch to it."""
    svc = services()
    info = await profiles.describe(svc)
    chosen = next(p for p in info["profiles"] if p["id"] == body.profile.value)
    try:
        if chosen["missing"]:
            profiles.start_install(svc, body.profile, list(chosen["missing"]))
        else:
            await profiles.apply(svc, body.profile)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return await profiles.describe(svc)
