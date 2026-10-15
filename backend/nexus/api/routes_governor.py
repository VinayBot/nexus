"""Resource Governor and reliability telemetry."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from nexus.core.event_types import GovernorMetrics
from nexus.core.services import services

router = APIRouter(prefix="/governor", tags=["governor"])


@router.get("/metrics", response_model=GovernorMetrics)
async def metrics() -> GovernorMetrics:
    return await services().governor.sample()


@router.get("/history")
async def history(limit: int = 300) -> list[dict[str, Any]]:
    return list(services().governor.history)[-limit:]


class LimitUpdate(BaseModel):
    limit: int = Field(ge=1, le=8)


@router.put("/limit", response_model=GovernorMetrics)
async def set_limit(body: LimitUpdate) -> GovernorMetrics:
    services().governor.set_limit(body.limit)
    return services().governor.metrics()


@router.get("/circuits")
async def circuits() -> list[dict[str, object]]:
    return services().breakers.snapshot()
