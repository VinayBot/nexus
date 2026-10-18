"""Switch the model profile at runtime (Settings → Models) and remember the choice.

The saved choice lives in ``<data_dir>/model_profile.json`` and wins over
``NEXUS_MODEL_PROFILE`` at the next start, because it is the owner's latest pick.
Switching unloads the previous profile's chat models from Ollama, so a 16 GB Mac
never holds two profiles in memory at once.
"""

from __future__ import annotations

import json
from typing import Any

from nexus.core.config import PROFILE_INFO, PROFILES, ModelProfile, ModelSet, fallback_for
from nexus.core.logging import get_logger

log = get_logger(__name__)
FILE = "model_profile.json"


def chat_models(models: ModelSet) -> set[str]:
    return {m for m in (models.main, models.fast, models.code, models.fallback) if m}


def saved_profile(data_dir: Any) -> ModelProfile | None:
    path = data_dir / FILE
    try:
        return ModelProfile(json.loads(path.read_text())["profile"])
    except (OSError, ValueError, KeyError):
        return None


async def installed_models(svc: Any) -> list[str]:
    try:
        return list(await svc.provider.available_models())
    except Exception:
        return []


def _installed(model: str, installed: list[str]) -> bool:
    return model in installed or f"{model}:latest" in installed


async def describe(svc: Any) -> dict[str, Any]:
    installed = await installed_models(svc)
    simulation = svc.settings.llm_provider == "simulation"
    profiles = []
    for pid, info in PROFILE_INFO.items():
        models = PROFILES[pid]
        needed = sorted(chat_models(models) | {models.embed})
        missing = [m for m in needed if not _installed(m, installed)]
        profiles.append(
            {
                "id": pid.value,
                **info,
                "models": models.model_dump(),
                "missing": [] if simulation else missing,
            }
        )
    return {
        "active": svc.extras.get("model_profile", svc.settings.model_profile.value),
        "models": svc.llm.router.models.model_dump(),
        "installed": installed,
        "profiles": profiles,
    }


async def apply(svc: Any, profile: ModelProfile, *, persist: bool = True) -> None:
    old = chat_models(svc.llm.router.models)
    models = PROFILES[profile]
    svc.llm.router.models = models
    svc.llm.fallback_model = fallback_for(models)
    svc.register("model_profile", profile.value)
    if persist:
        (svc.settings.data_dir / FILE).write_text(json.dumps({"profile": profile.value}))
    unload = getattr(svc.provider, "unload", None)
    if unload is not None:
        for model in old - chat_models(models):
            try:
                await unload(model)
            except Exception as exc:  # unloading is best effort
                log.warning("models.unload_failed", model=model, error=str(exc))
