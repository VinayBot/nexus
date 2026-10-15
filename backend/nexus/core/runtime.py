"""Runtime bootstrap: build every long-lived service in the right order.

Used by the FastAPI lifespan and by integration tests (with a ScriptedLLM and a
local toolbox) so both exercise exactly the same wiring.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from nexus.agents.registry import AgentRegistry
from nexus.agents.toolbox import ToolBox
from nexus.core.config import Settings, get_settings
from nexus.core.events import bus
from nexus.core.logging import get_logger
from nexus.core.meter import meter
from nexus.core.services import Services, build_services, set_services
from nexus.db import repo
from nexus.db.engine import Database
from nexus.graph.main_graph import build_graph
from nexus.graph.runner import MissionRunner
from nexus.hitl.approvals import ApprovalService
from nexus.hitl.email_approvals import EmailApprovals
from nexus.hitl.mailer import Mailer
from nexus.hitl.timetravel import TimeTravel
from nexus.hitl.tokens import TokenService
from nexus.llm.provider import LLMProvider
from nexus.safety.policies import PolicyEngine

log = get_logger(__name__)


@asynccontextmanager
async def runtime(
    settings: Settings | None = None,
    *,
    provider: LLMProvider | None = None,
    toolbox: ToolBox | None = None,
    recover: bool = True,
    memory: bool = True,
    extra_setup: Any = None,
) -> AsyncIterator[Services]:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    async with AsyncExitStack() as stack:
        svc = build_services(settings, provider)
        set_services(svc)

        db = Database(settings.sqlite_path)
        await db.init()
        stack.push_async_callback(db.close)
        svc.register("db", db)
        svc.register("registry", AgentRegistry(settings.data_dir / "agents"))
        svc.register("policies", PolicyEngine(settings.data_dir / "policies.yaml"))

        if memory:
            from nexus.memory.long_term import LongTermMemory

            svc.register("memory", LongTermMemory(settings.chroma_path, svc.llm.embed))

        bus.set_sink(lambda events: repo.save_events(db, events))
        bus.add_listener(meter.on_event)

        if toolbox is None:
            from nexus.mcp_servers.hub import start_mcp_hub

            toolbox = await stack.enter_async_context(start_mcp_hub(svc))
        svc.register("toolbox", toolbox)

        saver = await stack.enter_async_context(
            AsyncSqliteSaver.from_conn_string(str(settings.checkpoints_path))
        )
        graph = build_graph(saver)
        runner = MissionRunner(
            graph, db, token_cap=svc.policies.token_cap(settings.mission_token_limit)
        )
        svc.register("checkpointer", saver)
        svc.register("runner", runner)
        approvals = ApprovalService(db, runner)
        svc.register("approvals", approvals)
        svc.register("timetravel", TimeTravel(runner))
        tokens = TokenService(settings.secret_key, db)
        svc.register("tokens", tokens)
        mailer = svc.extras.get("mailer") or Mailer(db, settings.smtp_host, settings.smtp_port)
        svc.register("email_approvals", EmailApprovals(settings, approvals, mailer, tokens))
        if settings.secret_key == "dev-only-change-me":
            log.warning("security.default_secret", hint="set NEXUS_SECRET_KEY in .env")

        from nexus.playbooks.demo_service import DemoService

        svc.register("demo", DemoService(settings))
        from nexus.playbooks.ticket_solver import ensure_seed_tickets

        await ensure_seed_tickets(db)

        if extra_setup is not None:
            await extra_setup(svc, stack)

        stack.push_async_callback(bus.flush)
        stack.push_async_callback(runner.shutdown)
        if recover:
            resumed = await runner.recover()
            if resumed:
                log.info("runtime.recovered", missions=resumed)
        try:
            yield svc
        finally:
            set_services(None)
            bus.set_sink(None)
