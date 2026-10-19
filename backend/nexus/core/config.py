"""Application settings, loaded from environment variables and ``.env``.

Model names are never hard-coded elsewhere: every component asks
:func:`get_settings` for the model that serves a *role* (``main``, ``fast``,
``embed``). A *profile* supplies sensible defaults for a machine size, and any
individual ``NEXUS_MODEL_*`` variable overrides the profile.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class ModelProfile(StrEnum):
    """Pre-sized model sets. ``lite`` is the safe default on a busy 16 GB Mac."""

    LITE = "lite"
    BALANCED = "balanced"
    STANDARD = "standard"


class ModelSet(BaseModel):
    """Ollama tags for each model role."""

    main: str = Field(description="Planning, solving, coding and judging.")
    fast: str = Field(description="Rewrite, routing, grading, summarising, guide chat.")
    embed: str = Field(description="Embeddings for RAG and memory search.")
    code: str | None = Field(default=None, description="Code writing; None = the main model.")
    fallback: str | None = Field(default=None, description="Alternate model on failure.")


PROFILES: dict[ModelProfile, ModelSet] = {
    ModelProfile.LITE: ModelSet(main="llama3.2:3b", fast="llama3.2:3b", embed="nomic-embed-text"),
    # One general model for every non-code role plus a small coder: two chat models,
    # ~5 GB resident at peak — sized for a 16 GB Mac that also runs a browser and an IDE.
    # (qwen3:4b was tried and dropped: it always "thinks" first, even with think=False under
    # a JSON schema, so structured calls ran out of tokens or took minutes.)
    ModelProfile.BALANCED: ModelSet(
        main="qwen2.5:3b",
        fast="qwen2.5:3b",
        code="qwen2.5-coder:3b",
        embed="nomic-embed-text",
        fallback="llama3.2:3b",
    ),
    ModelProfile.STANDARD: ModelSet(
        main="qwen2.5-coder:7b", fast="llama3.2:3b", embed="nomic-embed-text"
    ),
}

#: Shown in Settings → Models.
PROFILE_INFO: dict[ModelProfile, dict[str, str | float]] = {
    ModelProfile.LITE: {
        "label": "Lite",
        "description": "llama3.2 3B for every role. Lowest memory, fastest, weakest writing.",
        "ram_gb": 3.0,
    },
    ModelProfile.BALANCED: {
        "label": "Balanced",
        "description": "Qwen2.5 3B for planning and writing, Qwen2.5-Coder 3B for code, "
        "llama3.2 as fallback. Stricter JSON and better code; recommended for a 16 GB Mac.",
        "ram_gb": 5.0,
    },
    ModelProfile.STANDARD: {
        "label": "Standard (7B)",
        "description": "Qwen2.5-Coder 7B main model. Strongest, but heavy for a 16 GB Mac "
        "that is also running a browser and an IDE.",
        "ram_gb": 7.5,
    },
}


class Settings(BaseSettings):
    """Process-wide configuration. Every field maps to a ``NEXUS_``-prefixed env var."""

    model_config = SettingsConfigDict(
        env_prefix="NEXUS_",
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        extra="ignore",
    )

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "WARNING"
    log_json: bool = False

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    data_dir: Path = BACKEND_ROOT / "data"

    ollama_base_url: str = "http://127.0.0.1:11434"
    model_profile: ModelProfile = ModelProfile.LITE
    llm_provider: Literal["ollama", "simulation"] = "ollama"
    model_main: str | None = None
    model_fast: str | None = None
    model_embed: str | None = None
    model_code: str | None = None
    num_ctx: int = Field(default=8192, ge=1024)

    model_fallback: str | None = Field(
        default=None, description="Alternate model tried after the primary fails."
    )
    llm_max_concurrency: int = Field(default=2, ge=1, le=8)
    llm_timeout_s: float = 180.0
    governor_elevated_below_gb: float = 2.0
    governor_critical_below_gb: float = 1.0

    public_url: str = "http://127.0.0.1:8000"
    ui_url: str = "http://localhost:3000"
    secret_key: str = "dev-only-change-me"
    smtp_host: str = "127.0.0.1"
    smtp_port: int = 1025
    #: Real delivery (e.g. Gmail: smtp.gmail.com, 587, your address, a 16-character App Password).
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = False
    #: Where mission results are emailed (also editable in Settings → Email results).
    result_email: str | None = None
    email_results: bool = True
    owner_email: str = "owner@nexus.local"
    sandbox_backend: Literal["docker", "local"] = "docker"
    sandbox_image: str = "nexus-sandbox:latest"
    github_token: str | None = None
    demo_service_port: int = 8100
    demo_autostart: bool = True
    auto_heal: bool = True
    mission_token_limit: int = 120_000
    pruning_strategy: Literal["sliding_window", "summarise"] = "summarise"
    #: Seconds the verifier watches demo-service health after a fix.
    verify_window_s: float = 12.0

    @property
    def models(self) -> ModelSet:
        """The profile's models with any explicit per-role overrides applied."""
        base = PROFILES[self.model_profile]
        return ModelSet(
            main=self.model_main or base.main,
            fast=self.model_fast or base.fast,
            embed=self.model_embed or base.embed,
            code=self.model_code or base.code,
            fallback=self.model_fallback or base.fallback,
        )

    @property
    def fallback_model(self) -> str | None:
        return fallback_for(self.models)

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "nexus.db"

    @property
    def checkpoints_path(self) -> Path:
        return self.data_dir / "checkpoints.db"

    @property
    def chroma_path(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def workspaces_path(self) -> Path:
        return self.data_dir / "workspaces"


def fallback_for(models: ModelSet) -> str | None:
    """The profile's alternate, else the fast model when it differs from main."""
    return models.fallback or (models.fast if models.fast != models.main else None)


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton; tests clear it with ``get_settings.cache_clear()``."""
    return Settings()
