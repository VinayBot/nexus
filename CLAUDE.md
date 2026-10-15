# NEXUS — project memory

Local-first multi-agent OS (Week-4 bootcamp project). LangGraph orchestration, Ollama models,
SQLite persistence, MCP tools, human approval gates, a "Sunset Command" UI where every Live
animation is driven by a real backend event. Checklist: `docs/PLAN.md`; topic → code map:
`docs/TOPIC_COVERAGE.md`; architecture: `docs/ARCHITECTURE.md`; decisions: `docs/adr/`.

## Stack
- **backend/** Python 3.12 + uv · FastAPI · LangGraph 1.2 (+ `langgraph-checkpoint-sqlite`) ·
  official `ollama` client behind our `LLMProvider` · `mcp` 2.x (`MCPServer`, in-process `Client`) ·
  SQLAlchemy async + aiosqlite · ChromaDB (only the backend process opens it) · tenacity · structlog.
- **frontend/** Next.js 15 App Router · TS strict (`noUncheckedIndexedAccess`) · Tailwind v4 with
  tokens in `src/styles/tokens.css` · motion · @xyflow/react · R3F (landing only, lazy) · zustand ·
  TanStack Query · pnpm 12 (build scripts allow-listed in `pnpm-workspace.yaml`).
- Ollama runs natively (not Docker). Docker (Colima here) is only for Mailpit and the sandbox image.

## Commands (from repo root)
`make setup` · `make models` · `make dev` (backend :8000, frontend :3000) · `make test` ·
`make lint` · `make typecheck` · `make check` (all) · `make e2e` · `make types` · `make reset`.
Compose CLI is `docker-compose` on this machine; the Makefile detects it.

## Conventions
- Model names only in config (`nexus/core/config.py` profiles). Default profile `lite`
  (llama3.2:3b) because the owner's 16 GB Mac has crashed under bigger models; `standard` = 7B.
- Every node is wrapped by `graph/instrument.py` so it emits node/reducer events; never emit
  events from inside reducers (they must stay pure).
- Live UI = real events only. Scripted motion exists only in Replay (recorded events) and the
  labelled Simulation mode.
- Tests use the deterministic `ScriptedLLM`; `@pytest.mark.live` tests need Ollama and are
  deselected by default. Open a runtime with MCP clients *inside* each test (not in an async
  fixture): anyio task groups must enter and exit in the same task.
- e2e (`make e2e`) starts its own backend in Simulation mode on :8011 and Next on :3011
  (`NEXT_DIST_DIR=.next-e2e`), so it never disturbs the dev servers. Animated elements must not
  be the click target (Playwright needs a stable element): animate an inner span.
- Small-model rules that made the live self-heal work: schema-constrained turns, line-range code
  edits with a traceback focus line, output-token caps on structured calls, test feedback into
  the next tournament round. Don't regress these.
- Files stay under ~400 lines; split instead. Pydantic models for every agent I/O.
- Untrusted text (tickets, docs, logs, tool output) is always wrapped by `safety.guardrails.fence()`.
- Approval email links: GET shows a confirm page, POST decides (link prefetchers must not approve).
- Commit at the end of each phase; tick `docs/PLAN.md`.
