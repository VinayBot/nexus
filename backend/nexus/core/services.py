"""Process-wide service container.

Built once at startup (``build_services``) and read anywhere via ``services()``.
Tests build their own container with a ``ScriptedLLM`` and install it with
``set_services``. Later phases attach more services (db, MCP hub, memory…) as
attributes so graph nodes need no constructor injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexus.core.config import Settings, get_settings
from nexus.core.governor import ResourceGovernor
from nexus.llm.gateway import LLMGateway
from nexus.llm.ollama_provider import OllamaProvider
from nexus.llm.provider import LLMProvider
from nexus.llm.router import ModelRouter
from nexus.reliability.circuit_breaker import BreakerRegistry


@dataclass
class Services:
    settings: Settings
    provider: LLMProvider
    governor: ResourceGovernor
    breakers: BreakerRegistry
    llm: LLMGateway
    extras: dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        # Late-bound services (db, mcp, memory, …) registered via `register`.
        extras = self.__dict__.get("extras", {})
        if name in extras:
            return extras[name]
        raise AttributeError(name)

    def register(self, name: str, value: Any) -> None:
        self.extras[name] = value


def build_services(
    settings: Settings | None = None, provider: LLMProvider | None = None
) -> Services:
    settings = settings or get_settings()
    if provider is None and settings.llm_provider == "simulation":
        from nexus.llm.simulation import simulation_llm

        provider = simulation_llm()
    provider = provider or OllamaProvider(
        settings.ollama_base_url, timeout_s=settings.llm_timeout_s
    )
    governor = ResourceGovernor(
        settings.llm_max_concurrency,
        elevated_below_gb=settings.governor_elevated_below_gb,
        critical_below_gb=settings.governor_critical_below_gb,
        loaded_models=provider.loaded_models,
    )
    breakers = BreakerRegistry()
    llm = LLMGateway(
        provider,
        ModelRouter(settings.models),
        governor,
        breakers,
        num_ctx=settings.num_ctx,
        timeout_s=settings.llm_timeout_s,
        fallback_model=settings.fallback_model,
        embed_model=settings.models.embed,
    )
    return Services(settings, provider, governor, breakers, llm)


_services: Services | None = None


def services() -> Services:
    if _services is None:
        raise RuntimeError("services not initialised; call set_services(build_services())")
    return _services


def set_services(s: Services | None) -> None:
    global _services
    _services = s
