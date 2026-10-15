"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus import __version__
from nexus.api import routes_governor, routes_system
from nexus.core.config import get_settings
from nexus.core.logging import configure_logging, get_logger
from nexus.core.services import build_services, set_services

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    svc = getattr(app.state, "services", None) or build_services(settings)
    set_services(svc)
    log.info(
        "nexus.start", profile=settings.model_profile.value, models=settings.models.model_dump()
    )
    monitor = asyncio.create_task(svc.governor.run(), name="governor")
    try:
        yield
    finally:
        monitor.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await monitor
        log.info("nexus.stop")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.log_json)
    app = FastAPI(
        title="NEXUS",
        version=__version__,
        description="Dynamic multi-agent operating system on local models.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (routes_system, routes_governor):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
