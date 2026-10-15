"""Response models for the system endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CheckStatus = Literal["ok", "degraded", "down"]


class Liveness(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class DependencyCheck(BaseModel):
    name: str
    status: CheckStatus
    detail: str


class Readiness(BaseModel):
    """Overall status is the worst of the individual checks."""

    status: CheckStatus
    checks: list[DependencyCheck]


class ModelRoles(BaseModel):
    main: str
    fast: str
    embed: str


class SystemInfo(BaseModel):
    version: str
    env: str
    model_profile: str
    models: ModelRoles
    num_ctx: int
    llm_max_concurrency: int
