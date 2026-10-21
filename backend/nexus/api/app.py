"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from nexus import __version__
from nexus.api import (
    errors,
    routes_approvals,
    routes_auth,
    routes_chaos,
    routes_governor,
    routes_graph,
    routes_guide,
    routes_hitl,
    routes_insight,
    routes_mcp,
    routes_memory,
    routes_metrics,
    routes_missions,
    routes_notify,
    routes_system,
    routes_work,
    ws,
)
from nexus.api.request_id import RequestIdMiddleware
from nexus.api.security_headers import SecurityHeadersMiddleware
from nexus.auth.guard import guard
from nexus.core.config import get_settings
from nexus.core.logging import configure_logging, get_logger
from nexus.core.runtime import runtime
from nexus.memory.long_term import index_docs, project_doc_paths
from nexus.playbooks.watcher import Watcher

log = get_logger(__name__)


async def _index_docs_later(svc: object) -> None:
    await asyncio.sleep(2)  # let the API come up first
    memory = getattr(svc, "extras", {}).get("memory")
    if memory is None:
        return
    try:
        added = await index_docs(memory, project_doc_paths())
        log.info("docs.indexed", chunks_added=added)
    except Exception as exc:  # noqa: BLE001 - indexing docs is optional at startup
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
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(SecurityHeadersMiddleware, frame_origins=settings.cors_origins)
    app.add_middleware(RequestIdMiddleware)  # outermost: every response carries the id
    errors.install(app)
    # event logs and summaries run to 100+ KB of JSON; SSE streams are excluded by Starlette
    app.add_middleware(GZipMiddleware, minimum_size=2048, compresslevel=5)
    # every API route passes the RBAC guard (auth/policy.py decides public / viewer / ...)
    protected = [Depends(guard)]
    app.include_router(routes_auth.router, prefix="/api/v1", dependencies=protected)
    for module in (
        routes_system,
        routes_governor,
        routes_missions,
        routes_approvals,
        routes_chaos,
        routes_graph,
        routes_guide,
        routes_hitl,
        routes_insight,
        routes_notify,
        routes_mcp,
        routes_memory,
        routes_work,
    ):
        app.include_router(module.router, prefix="/api/v1", dependencies=protected)
    app.include_router(ws.router)
    app.include_router(routes_metrics.router)  # Prometheus scrape target: GET /metrics
    # pages published by the Web Page Builder (static, no scripts) — /sites/<mission>/
    sites = settings.data_dir / "sites"
    sites.mkdir(parents=True, exist_ok=True)
    app.mount("/sites", StaticFiles(directory=sites, html=True), name="sites")
    return app


app = create_app()
