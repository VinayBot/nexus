# Build plan

Ticked = implemented, tested and committed. Phases follow spec §18.

## Phase 0 — Foundations
- [x] Monorepo scaffold, `CLAUDE.md`, this plan
- [x] Backend: uv project, settings with model profiles, structlog, `/health`, `/health/ready`, `/system/info`
- [x] Tooling: ruff, mypy strict, pytest; ESLint, Prettier, tsc strict, Vitest
- [x] Makefile, docker-compose skeleton (backend, frontend, mailpit, sandbox-runner, phoenix profile), `.env.example`
- [x] `scripts/ollama_env.sh`, `scripts/pull_models.sh`, `scripts/dev.sh`
- [x] Design tokens, fonts, themed shell (nav, top bar, procedural sunset skyline, embers)

## Phase 1 — LLM layer & raw SDK agent
- [x] `LLMProvider` interface + Ollama provider (streaming, timeouts) + scripted fake
- [x] Model router (role → model, escalation after 2 validation failures, routing events)
- [x] Resource Governor (adaptive semaphore, psutil, loaded models, tokens/sec, metrics API)
- [x] Token counting + budgets
- [x] Reliability: tenacity retries, JSON repair, validation re-prompt, circuit breaker, fallback chain
- [x] Raw SDK ReAct agent (httpx only) + tests

## Phase 2 — LangGraph core, persistence, events
- [x] `MissionState` + documented, tested reducers
- [x] Main graph (intake → rewrite → route → plan → assemble → dispatch ⇄ workers → … → report)
- [x] ReAct worker subgraph
- [x] AsyncSqliteSaver checkpoints; resume unfinished missions on startup
- [x] Event bus, event persistence, WebSockets (per mission + global, resume from seq)
- [x] Sliding-window + summarisation pruning with events
- [x] Missions API

## Phase 3 — MCP servers & tools
- [x] workspace-fs (path jail), sandbox-exec (Docker / labelled local fallback), knowledge, tickets, notify, observability
- [x] MCP hub (in-process clients), per-agent allowlists, call log
- [x] Sandbox runner image (Dockerfile; Docker path written, local labelled fallback verified — Colima was not running)
- [x] Armory API

## Phase 4 — Tournament + HITL + safety
- [x] Council/Tournament subgraph (parallel proposals, sandbox grounding, anonymised review, debate cycle, judge, escalation) — code-mode grounding exercised by the Self-Healing playbook in phase 5
- [x] Risk scorer, policy engine, guardrails (injection filter, redaction, allowlists)
- [x] Interrupts + approvals (UI + signed single-use email links via Mailpit)
- [x] Time travel (history, re-run, fork, compare) + audit log

## Phase 5 — Playbooks
- [x] demo-service with chaos switches, managed by the backend
- [x] Self-Healing (watcher, investigation, reproduction, tournament, approval, apply, verify, rollback, Fix Library)
- [x] Ticket Solver (mock tickets + optional GitHub)
- [x] Project Builder (scoped, ≤10 files, zip)
- [x] Council Q&A, Dynamic Mission (team approval, save as playbook)
- [x] Reputation updates

## Phase 6 — Frontend core
- [x] Event types generated from backend JSON Schema; WS client with resume
- [x] Robot SVG system + event-driven animation state machine
- [x] Mission Control (composer, Dojo Floor, Thought Stream, timeline)
- [x] Live Graph + State Inspector
- [x] Approvals (hanko stamp), Scroll of Time

## Phase 7 — Advanced screens
- [ ] Council Arena, Memory Palace, Barracks, Armory, Chaos Shrine, Observatory, Evals
- [ ] Architecture Explorer, Curriculum Map, Under the Hood, Settings, 3D landing hero

## Phase 8 — Hikari guide + polish
- [ ] Guide chat (RAG + live-state tools + UI actions + tours)
- [ ] Command palette, Presentation Mode, sound, Replay speed control
- [ ] Reduced motion, performance mode, accessibility, empty/loading/error states

## Phase 9 — Quality & docs
- [ ] Full test suite + Playwright e2e, GitHub Actions
- [ ] README, ARCHITECTURE.md, ADRs, TOPIC_COVERAGE.md, DEMO_SCRIPT.md, limitations
