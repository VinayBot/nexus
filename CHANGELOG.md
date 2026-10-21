# Changelog

All notable changes, newest first. Versions follow [Semantic Versioning](https://semver.org).

## [1.0.0] - 2026-10-21

Submission release for Week 4 (agentic systems, state machines and MCP).

### Added
- Native tool calling in the LangGraph ReAct worker (`tools=[JSON Schema]` → `tool_calls`
  → `role="tool"`), with recovery of calls a 3B model writes as text. `NEXUS_REACT_MODE=auto`
  picks native or JSON turns per model from a measured benchmark
  (`python -m nexus.evals.react_modes`).
- Optional PostgreSQL for app data and LangGraph checkpoints (`NEXUS_DATABASE_URL`), a
  `docker-compose.postgres.yml` override, and a CI job running the full suite on Postgres 16.
- Alembic schema migrations, applied on startup; older databases are stamped and upgraded.
- Accounts with Argon2id and JWT sessions, three roles (viewer, operator, owner) enforced by
  one policy table, and server-side sign-out (revoked token ids).
- Per-user limits: missions per minute and a daily token quota. Limits are stored in the
  database, so they survive restarts and are shared by replicas.
- `X-Request-ID` on every response and log line; one error shape with `request_id`.
- Security headers (CSP, nosniff, frame-deny; published pages may not run scripts).
- Typed response models for missions, events, state, auth, users, audit and time travel.
- Prometheus `/metrics`, an MCP server over stdio, and non-root Docker images with health checks.
- CI: 80% coverage gate, pip-audit, pnpm audit, CodeQL, Dependabot and pre-commit hooks.

### Fixed
- Lost first events between the history fetch and the WebSocket subscription.
- A SQLite-only JSON query and cross-event-loop connection reuse in the stdio MCP server
  (both found by the PostgreSQL job).
- The approval race, false incidents after sleep, and email rules for waiting missions.

## [0.9.0] - 2026-10-20
- Sign in with Google (Gmail API, `gmail.send` only) and prompt-driven result emails.
- Create Ticket mission; approvals by email (confirm page, single-use signed links).

## [0.8.0] - 2026-10-19
- Web Page Builder playbook, keyword routing, model profiles with one-click install.
- Clean Studio UI, approval pop-up on any screen, structured results.

## [0.5.0] - 2026-10-16
- End-to-end tests, CI, simulation mode, the guide and tours, replay, tracing, evals.

## [0.1.0] - 2026-10-15
- LLM gateway with retries, fallbacks and circuit breakers; Resource Governor.
- LangGraph core: typed state, reducers, `Send` fan-out, subgraphs, `interrupt()` approvals,
  SQLite checkpoints, time travel; seven MCP servers.
