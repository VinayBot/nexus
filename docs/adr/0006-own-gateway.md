# ADR 0006 — Our own LLM gateway over the official ollama client

**Status:** accepted

## Context
Every model call needs the same treatment: model routing, a governor slot, circuit
breaker, retries, fallback chain, token accounting, a token cap, streaming events and
tracing.

## Decision
- Use the official `ollama` client behind a small `LLMProvider` protocol, with a
  `LLMGateway` that every agent, node and tool uses. This replaces LangChain's
  `ChatOllama`.
- Structured outputs use Ollama's JSON-schema `format` plus our own validation re-prompt.

## Consequences
- One place to reason about reliability and cost; a scripted provider makes tests and
  Simulation mode trivial.
- LangChain is used only for `langchain_core` message types inside LangGraph state.
