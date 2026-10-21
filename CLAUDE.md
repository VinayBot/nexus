# NEXUS — project memory

Local-first multi-agent OS (Week-4 bootcamp project). LangGraph orchestration, Ollama models,
SQLite persistence, MCP tools, human approval gates, a calm professional "Studio" UI where every Live
animation is driven by a real backend event. Mission guide: `docs/HOW_IT_WORKS.md`; code walkthrough:
`docs/CODE_WALKTHROUGH.md`. Checklist: `docs/PLAN.md`; topic → code map:
`docs/TOPIC_COVERAGE.md`; architecture: `docs/ARCHITECTURE.md`; decisions: `docs/adr/`.

## Stack
- **backend/** Python 3.12 + uv · FastAPI · LangGraph 1.2 (+ `langgraph-checkpoint-sqlite`) ·
  official `ollama` client behind our `LLMProvider` · `mcp` 2.x (`MCPServer`, in-process `Client`) ·
  SQLAlchemy async + aiosqlite · ChromaDB (only the backend process opens it) · tenacity · structlog.
- **frontend/** Next.js 15 App Router · TS strict (`noUncheckedIndexedAccess`) · Tailwind v4 with
  tokens in `src/styles/tokens.css` · motion · @xyflow/react · zustand ·
  TanStack Query · pnpm 12 (build scripts allow-listed in `pnpm-workspace.yaml`).
- Ollama runs natively (not Docker). Docker (Colima here) is only for Mailpit and the sandbox image.

## Commands (from repo root)
`make setup` · `make models` · `make dev` (backend :8000, frontend :3000, Turbopack) ·
`make prod` (optimised build, no reloader — fastest) · `make test` ·
`make lint` · `make typecheck` · `make check` (all) · `make e2e` · `make types` · `make reset`.
Compose CLI is `docker-compose` on this machine; the Makefile detects it.

## Conventions
- Model names only in config (`nexus/core/config.py` profiles): `lite` (llama3.2:3b), `balanced`
  (qwen2.5:3b + qwen2.5-coder:3b for the `code` role, llama3.2 fallback), `standard` (7B, not pulled:
  the owner's 16 GB Mac crashed under bigger models). The owner's pick in Settings → Models is saved
  to `data/model_profile.json` and wins over `NEXUS_MODEL_PROFILE`. Avoid "thinking" models (qwen3):
  they think even with think=False under a JSON schema and blow the token caps.
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
- Theme "Studio": warm charcoal base, one accent from channel tokens (`--accent-rgb`,
  `--accent-soft-rgb`, `--accent-strong`; use `rgb(var(--accent-rgb)/0.15)`, never a literal colour)
  for nav and primary actions; presets Ember orange (default, owner preference), Violet, Emerald, Teal, Rose via
  `data-accent`; the scenery tokens (`--ember-rgb`, `--gold-rgb`, sky) follow the accent; status colours only for status. Plain sentence-case headings, no HUD brackets/scanlines.
  The sunset palette is only for the robots' mission floor and the landing page. Keep animations
  (lift, sweep, springs). Only floating elements (`.glass`) use backdrop blur.
- Approvals: `ApprovalPrompt` pops a dialog on any screen for approvals raised this session; the
  top-bar "N waiting" button reopens it; `QuickApproval` is reused inline in Mission Control.
- Results read: You asked → outcome sentence → output (page/zip/answer) → How the team did it.
  Report highlights are plain English (`graph/nodes/finish.py`).
- Email is prompt-driven: `hitl/email_intent.py` parses "…send the output to a@b.com" at
  `runner.create` (inputs.email_requested/email_to/email_self) and strips it from the agents'
  task. Results via `hitl/result_email.py` (runner `finished_hooks`), body in `email_body.py`;
  approval emails only for such missions, only to the owner. Sending: Sign in with Google
  (`hitl/google_mail.py`, Gmail API, scope gmail.send, token in `data/google.json` 0600) or
  SMTP. Nothing secret is ever returned by the API.
- Logs are quiet by default (`NEXUS_LOG_LEVEL=WARNING`, no uvicorn access log); set INFO to debug.
- Approval email links: GET shows a confirm page, POST decides (link prefetchers must not approve).
- Commit at the end of each phase; tick `docs/PLAN.md`.
