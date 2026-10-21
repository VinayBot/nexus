# Topic coverage (Week 4, Days 16–20)

Each concept: where it is implemented (paths under `backend/nexus/` unless noted), the
test that proves it, and where to see it in the UI. The in-app **Curriculum Map**
(`/learn`) shows the same table, plus live counts of the events that prove each
concept ran on this machine.

## Day 16 — Multi-Agent Systems

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| ReAct (Reason–Act–Observe) | `graph/subgraphs/react_worker.py` — `think` ⇄ `act`, `finalize` on the iteration guard; turns use native tool calling or schema-constrained JSON (`NEXUS_REACT_MODE`; `auto` picks per model from the benchmark) | `test_graph_missions.py::test_react_iteration_guard_forces_final`, `::test_council_qa_runs_end_to_end` | Missions screen → Activity panel (Thought / Action / Observation chips) |
| Plan-and-Execute | `graph/nodes/planning.py::plan` (typed `Plan`, replanner revisions), `graph/nodes/work.py::dispatch` (executes ready steps by dependency) | `test_validation_failures_hit_fix_and_replan_guards`, `test_playbooks.py::test_project_builder_builds_tests_and_packages` (dependency waves) | Live Graph (`plan`, `dispatch` ×N); Activity panel "Plan r0/r1" |
| Raw SDK agent (no framework) | `llm/raw_react_agent.py` (httpx only: loop, retries, step limit) | `test_raw_agent.py` (+ `@live` against Ollama) | Under the Hood; Benchmarks "Raw SDK vs LangGraph" |
| Native tool calling | **In the LangGraph worker** (`react_worker.py::_native_turn`; `auto` uses it for Qwen-family models) and the raw SDK agent (`raw_react_agent.py::_run_native`): `tools=[JSON Schema]` → structured `tool_calls` → `role="tool"` results; a reply without tool calls is the answer. Calls a 3B model prints as text (JSON or `tool(arg=…)`) are recovered (`llm/text_tool_calls.py`); an empty reply falls back to one JSON turn | `test_react_native.py` (round trip, text recovery, fallback, JSON mode, `@live` on qwen2.5:3b and llama3.2:3b), `test_raw_agent.py::test_native_tool_calling_loop`; measured in `docs/benchmarks/react_modes.json` | Activity panel (Action chips); Under the Hood |
| Conditional routing | `graph/nodes/understand.py::route/after_route`; `after_validate`, `after_gate`, `after_approval`, `after_verify`, `after_rollback` | `test_router_picks_playbook_and_emits_edge`, `test_hitl.py` (risk routes) | Live Graph — the chosen branch label flashes on the edge |

## Day 17 — LangGraph core: states & cycles

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| State machine, typed state | `graph/state.py::MissionState`, `graph/main_graph.py::build_graph` (20 nodes) | all graph tests | Live Graph + State Inspector |
| Reducers | `graph/reducers.py` — `merge_dict`, `merge_scores`, `dedupe_append`, `sum_counts`, `append_list`, `add_messages` | `test_units_core.py` reducer tests; parallel fan-in asserted in `test_council_qa_runs_end_to_end` | State Inspector "Reducer merges" (which reducer merged what, live) |
| Conditional edges | `add_conditional_edges` for route, assemble, collect, validate, risk gate, approval, execute, verify, rollback | as above | Live Graph (dashed edges = conditional) |
| Cycles with guards | `state.DEFAULT_LIMITS` (clarify, dispatch, fix, replan, verify, debate, react), counters in `state.loops` (`sum_counts`) | `test_validation_failures_hit_fix_and_replan_guards`, `test_react_iteration_guard_forces_final`, `test_self_healing.py::test_failed_verification_rolls_back` | Live Graph ×N iteration badges; Stage strip counters |
| Parallel fan-out / fan-in | `dispatch` returns `Command(goto=[Send("worker", …)])`; `collect` is the fan-in; the tournament uses `Send` for solvers and reviewers | `test_council_qa_runs_end_to_end` (2 workers, 3 solvers, 3 reviews each) | Mission Floor (data orbs fly to several workers at once, "Send ×N") |
| Subgraphs | `react_worker`, `tournament` (compiled graphs invoked by nodes; structures exported to the UI) | graph tests | Live Graph (worker/council marked as subgraphs) |
| Command handoffs | `dispatch` → `Command(goto=…, update=…)` | graph tests | Activity panel "Handoff commander → agent" |

## Day 18 — Memory systems & context pruning

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| Persistence (SQLite or PostgreSQL) | `db/checkpoints.py::open_checkpointer` — `AsyncSqliteSaver` by default, `AsyncPostgresSaver` when `NEXUS_DATABASE_URL` is set; app tables in `db/models.py` (dialect-aware upserts in `db/engine.py`) | `test_crashed_mission_resumes_from_sqlite_checkpoint`; the whole suite also runs on PostgreSQL 16 in CI (`make test-postgres`) | Time Travel; checkpoint nodes in Missions screen |
| Crash resume | `graph/runner.py::recover()` on startup; shutdown keeps missions "running" | same test (planning is not redone after restart); also verified live when a dev reload restarted the backend mid-mission | "Mission resumed from checkpoint" in the Activity panel |
| Sliding-window pruning | `memory/pruning.py::sliding_window` (system + pinned + recent) | `test_sliding_window_keeps_system_pinned_and_recent` | Memory (vessels, pruning events) |
| Summarisation pruning | `memory/pruning.py::summarise` (rolling pinned summary, fallback to the window) | `test_summarise_folds_old_turns_into_pinned_summary`, `test_summarise_failure_falls_back_to_sliding_window` | Memory; Benchmarks "pruning" suite |
| Token limits / budgets | `llm/tokens.py` (estimates calibrated against Ollama's `prompt_eval_count`, `TokenBudget`), `core/meter.py` (per-mission cap from policy) | `test_token_estimates_learn_from_real_counts`, `test_budget_window_and_record`; the cap stopped a real mission at 124,576 / 120,000 tokens | Observatory; State Inspector token bars |
| Long-term memory | `memory/long_term.py` (Chroma: `fix_library`, `missions`, `docs`, `lessons`; PCA map) | `test_mcp.py::test_knowledge_search`, `test_self_healing_end_to_end` (Fix Library write) | Memory library, search and embedding map |

## Day 19 — Multi-agent workflows & MCP

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| Supervisor routing | `planning.py::assemble` (reputation-aware team), `work.py::dispatch` (the Commander hands off steps) | graph tests | Mission Floor (Commander on the dais) |
| Worker delegation | `work.py::worker` → ReAct subgraph per step with a per-agent tool allowlist | graph tests | Activity panel; Agents (allowlists) |
| Custom MCP servers | `mcp_servers/` — workspace (path jail), sandbox, knowledge, tickets (+GitHub), notify (system-only), observability, demo; `hub.py` | `test_mcp.py` (all servers, path jail, allowlist, notify guard, sandbox, tickets) | Tools (servers, tools, schemas, health, call log, "try tool") |
| MCP transport (stdio, JSON-RPC) | `mcp_servers/__main__.py` serves any server over stdio (`python -m nexus.mcp_servers tickets`) for external clients; the app hub uses in-process clients | `test_mcp_stdio.py` (spawns the server as a process, `list_tools`, `create` + `get` a ticket over stdio) | — |

## Day 20 — Human-in-the-loop & safety

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| State interrupts | `interrupt()` in `clarify`, `assemble` (team), `approval`; resumed with `Command(resume=…)` in `runner.resume` | `test_vague_task_interrupts_for_clarification_then_resumes`, `test_dynamic_mission_requires_team_approval…` | Approvals; "Awaiting your approval" in Missions screen |
| Approval gates | `safety/risk.py` + `policies.yaml` route to approval; `hitl/approvals.py` | `test_hitl.py` (approve, reject, CRITICAL override) | Approvals (risk gauge, APPROVED stamp) |
| E-mail approvals | `hitl/tokens.py` (signed, expiring, single-use), `hitl/email_approvals.py` (GET confirm, POST decide), Mailpit | `test_approval_email_link_resumes_mission_and_is_single_use`, `test_tampered_and_expired_tokens_are_rejected` | Mailpit inbox; e-mail status chip on approval cards |
| Time travel | `hitl/timetravel.py` — history tree, `state_at`, re-run, fork via `update_state`, choose runner-up, compare | `test_time_travel_runner_up_fork_and_compare`, `test_fork_with_state_patch_reruns_from_checkpoint`; e2e `timetravel.spec.ts` | Time Travel |
| Safety | guardrails (injection, redaction, fencing), allowlists, path jail, sandbox, policies, audit log | `test_units_core.py` guardrail and risk tests; `test_ticket_injection_is_flagged` | Settings → Policies; Audit log tab |
| Who may approve (RBAC) | `auth/` — Argon2id passwords, JWT sessions, roles owner / operator / viewer checked by one policy table on every route (`auth/policy.py`); approvals record the real username; login rate limit; WebSockets need a session | `test_auth.py` (role matrix, spoofed `by` ignored, rate limit, WS 4401, last-owner rule); e2e `auth.spec.ts` | Sign-in page; Settings → Users; read-only controls for viewers |

## Brief — reliability with local open models

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| Automated retries | transport (`reliability/retry.py`, tenacity, jitter, events), node (`RetryPolicy`), validation re-prompts (`gateway.structured`), JSON repair | `test_reliability.py`, `test_llm_gateway.py` | Robots glitch (RGB split) with an ×N badge; Observatory "retries absorbed" |
| Fallbacks | primary → alternate model → reduced context (`gateway.complete`); safe defaults; dead letters with "retry from here" | `test_fallback_chain_alternate_model_then_reduced_context` | Observatory |
| Circuit breakers | `reliability/circuit_breaker.py` per model | `test_circuit_breaker_*`, `test_all_fallbacks_failing_raises_and_opens_circuit` | Observatory circuit list |
| Local open models | Ollama provider, model router (fast/main), Resource Governor | `test_router_*`, governor tests | System Power gauge; Settings |

## Production readiness (from the Week 1–2 report cards)

| Concern | Implementation | Tests |
|---|---|---|
| Auth and RBAC | see "Who may approve" above | `test_auth.py`, `auth.spec.ts` |
| Observability | Prometheus `GET /metrics` (`api/routes_metrics.py`): missions, tokens, approvals, emails, RAM, concurrency, queue, tokens/s, circuit breakers; OpenTelemetry traces; Insights | `/metrics` scraped in the live check |
| Containers | non-root images with health checks, compose `service_healthy` ordering, root `.dockerignore` keeps `backend/data` (DB, tokens, keys) out of images | `docker compose build` |
| CI | `.github/workflows/ci.yml`: ruff, mypy --strict, pytest with an 80% coverage gate (82% now), the suite again on PostgreSQL 16, pip-audit, pnpm audit, eslint, tsc, vitest, Playwright; CodeQL (`codeql.yml`), Dependabot, pre-commit hooks | every push |
| Scalability | optional PostgreSQL for app data and checkpoints (pooled asyncpg engine), so several backend replicas can share one store | PostgreSQL CI job |
| Abuse limits | per user: missions per minute (429 + `Retry-After`) and a daily token quota (`auth/quotas.py`); per mission: the token cap; login: 5 per minute. Stored in the database (`auth/ratelimit.py`, `rate_hits`), so limits survive restarts and are shared by replicas | `test_quotas.py`, `test_hardening.py::test_rate_limit_survives_a_restart` |
| Schema migrations | Alembic (`db/migrations`), applied on startup; older databases are stamped at the baseline and upgraded | `test_hardening.py::test_migrations_build_exactly_the_model_schema`, `::test_database_from_before_migrations_is_stamped_then_upgraded` |
| Session revocation | `jti` in every JWT; `POST /auth/logout` → `revoked_tokens`; checked by the guard | `test_hardening.py::test_logout_revokes_the_token` |
| HTTP security headers | `api/security_headers.py`: CSP, nosniff, frame-deny; published pages `script-src 'none'` | `test_hardening.py::test_security_headers` |
| Error contract | `api/errors.py`: `{"detail", "request_id"}` for 4xx/5xx; unexpected errors logged, never leaked | `test_hardening.py::test_errors_carry_the_request_id`; `frontend/src/lib/__tests__/api.test.ts` |
| Traceability | `X-Request-ID` accepted or generated, bound to every log line, echoed on the response (`api/request_id.py`) | `test_quotas.py::test_request_id_is_echoed_or_generated` |
| SDLC | Conventional Commits, PR and issue templates, CHANGELOG, CONTRIBUTING, SECURITY policy, tagged release `v1.0.0` | — |
| API contracts | Pydantic response models for missions, events, state, auth, users, audit, time travel (`api/schemas.py`) | OpenAPI at `/docs` |
| DB performance | one query per list endpoint (no N+1); index on `missions.created_at` | — |
| Secrets | weak or placeholder `NEXUS_SECRET_KEY` → random 48-byte key in `data/secret.key` (0600) | `test_weak_secret_is_replaced_by_a_strong_private_key` |
