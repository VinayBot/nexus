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

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class ModelProfile(StrEnum):
    """Pre-sized model sets. ``lite`` is the safe default on a busy 16 GB Mac."""

    LITE = "lite"
    STANDARD = "standard"


class ModelSet(BaseModel):
    """Ollama tags for each model role."""

    main: str = Field(description="Planning, solving, coding and judging.")
    fast: str = Field(description="Rewrite, routing, grading, summarising, guide chat.")
    embed: str = Field(description="Embeddings for RAG and memory search.")


PROFILES: dict[ModelProfile, ModelSet] = {
    ModelProfile.LITE: ModelSet(main="llama3.2:3b", fast="llama3.2:3b", embed="nomic-embed-text"),
    ModelProfile.STANDARD: ModelSet(
        main="qwen2.5-coder:7b", fast="llama3.2:3b", embed="nomic-embed-text"
    ),
}


class Settings(BaseSettings):
    """Process-wide configuration. Every field maps to a ``NEXUS_``-prefixed env var."""

    model_config = SettingsConfigDict(
        env_prefix="NEXUS_",
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        extra="ignore",
    )

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    log_json: bool = False

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    data_dir: Path = BACKEND_ROOT / "data"

    ollama_base_url: str = "http://127.0.0.1:11434"
    model_profile: ModelProfile = ModelProfile.LITE
    model_main: str | None = None
    model_fast: str | None = None
    model_embed: str | None = None
    num_ctx: int = Field(default=8192, ge=1024)

    llm_max_concurrency: int = Field(default=2, ge=1, le=8)

    @property
    def models(self) -> ModelSet:
        """The profile's models with any explicit per-role overrides applied."""
        base = PROFILES[self.model_profile]
        return ModelSet(
            main=self.model_main or base.main,
            fast=self.model_fast or base.fast,
            embed=self.model_embed or base.embed,
        )

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "nexus.db"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton; tests clear it with ``get_settings.cache_clear()``."""
    return Settings()
