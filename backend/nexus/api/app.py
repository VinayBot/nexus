"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexus import __version__
from nexus.api import (
    routes_approvals,
    routes_chaos,
    routes_governor,
    routes_graph,
    routes_hitl,
    routes_mcp,
    routes_memory,
    routes_missions,
    routes_system,
    routes_work,
    ws,
)
from nexus.core.config import PROJECT_ROOT, get_settings
from nexus.core.logging import configure_logging, get_logger
from nexus.core.runtime import runtime
from nexus.memory.long_term import index_docs
from nexus.playbooks.watcher import Watcher

log = get_logger(__name__)

DOC_PATHS = [PROJECT_ROOT / "README.md", *sorted((PROJECT_ROOT / "docs").glob("*.md"))]


async def _index_docs_later(svc: object) -> None:
    await asyncio.sleep(2)  # let the API come up first
    memory = getattr(svc, "extras", {}).get("memory")
    if memory is None:
        return
    try:
        paths = [*DOC_PATHS, *sorted((PROJECT_ROOT / "docs" / "adr").glob("*.md"))]
        added = await index_docs(memory, paths)
        log.info("docs.indexed", chunks_added=added)
    except Exception as exc:
        log.warning("docs.index_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log.info(
        "nexus.start", profile=settings.model_profile.value, models=settings.models.model_dump()
    )
    async with runtime(settings) as svc:
        app.state.services = svc
        background = [
            asyncio.create_task(svc.governor.run(), name="governor"),
            asyncio.create_task(_index_docs_later(svc), name="index-docs"),
        ]
        if settings.demo_autostart:
            await svc.demo.start()
            watcher = Watcher(svc.demo, svc.db, svc.runner, auto_heal=settings.auto_heal)
            svc.register("watcher", watcher)
            background.append(asyncio.create_task(watcher.run(), name="watcher"))
        try:
            yield
        finally:
            await svc.demo.stop()
            for task in background:
                task.cancel()
            for task in background:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
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
    for module in (
        routes_system,
        routes_governor,
        routes_missions,
        routes_approvals,
        routes_chaos,
        routes_graph,
        routes_hitl,
        routes_mcp,
        routes_memory,
        routes_work,
    ):
        app.include_router(module.router, prefix="/api/v1")
    app.include_router(ws.router)
    return app


app = create_app()
