# NEXUS: a multi-agent workspace on local models

A team of 14 AI agents that plans, writes, codes, tests and asks a human before anything
risky, built on **LangGraph** with **local models (Ollama)**, **MCP tools**, **human-in-the-loop
approvals**, **checkpoints and time travel**, and a live UI where every animation is a real
backend event. Week 4 assignment (Agentic systems, state machines and MCP), AI Engineering
Bootcamp.

![Mission result](docs/images/mission-result.png)

**What you can ask it**

| Mission | Example | What you get |
|---|---|---|
| Web page | "Build an HTML page with a blog about AI" | A styled page, published with a link and a live preview |
| Question | "When should a team prefer optimistic locking?" | A council answer: 3 agents, anonymous review, a judge |
| Fix service | Switch on a bug in the Chaos Lab | The bug found, fixed with tests, approved, applied and verified on live traffic |
| Build API | "Build a FastAPI API to manage books (title, author, year)" | A tested project as a zip |
| New ticket / Solve ticket | "Create a ticket for the slow inventory check" / "Solve ticket T-101" | A filed bug report, or a fix with tests posted to the ticket |
| Custom team | Anything else | The Commander designs a team; you approve it first |

Add "…and send the output to name@example.com" to any prompt to get the result by email.

---

## Quick start

**Needs:** macOS or Linux, Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22 with
pnpm (via corepack), and [Ollama](https://ollama.com/download). 16 GB RAM is enough.

```bash
git clone https://github.com/VinayBot/nexus.git && cd nexus
make setup            # backend deps (uv), frontend deps (pnpm), creates .env from .env.example
make models           # pulls llama3.2:3b + nomic-embed-text (the "lite" profile, ~2.3 GB)
make dev              # backend http://127.0.0.1:8000 · app http://localhost:3000
```

Open http://localhost:3000 → **Enter Command Center** → create the **owner account** (first
run only) → type a mission → **Start mission**.

Recommended models: in **Settings → Models** pick **Balanced** (Qwen2.5 3B + Qwen2.5-Coder
3B, ~5 GB), or `ollama pull qwen2.5:3b qwen2.5-coder:3b` first. **Standard (7B)** downloads
from the same screen when you want it.

<details>
<summary>Other ways to run</summary>

```bash
make prod                       # optimised frontend build + backend without the reloader
make check                      # everything CI runs: lint, mypy --strict, tsc, all tests
make e2e                        # Playwright end-to-end tests (own servers on :8011/:3011)
make test-postgres              # the backend suite against a throwaway PostgreSQL 16
make audit                      # known-vulnerability scan (pip-audit, pnpm audit)
docker compose up --build       # backend + frontend + Mailpit; Ollama stays native on the host
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build   # … on PostgreSQL
NEXUS_LLM_PROVIDER=simulation make dev   # no models needed: scripted, clearly labelled
```
</details>

### Configuration

All settings are `NEXUS_*` environment variables in `.env` (see [.env.example](.env.example)).
The important ones:

| Variable | Default | Meaning |
|---|---|---|
| `NEXUS_MODEL_PROFILE` | `lite` | `lite`, `balanced` or `standard`; Settings → Models switches it live |
| `NEXUS_AUTH_ENABLED` | `true` | accounts and roles; `false` only for throwaway demos |
| `NEXUS_BOOTSTRAP_USERS` | – | seed accounts: `alice:password:owner,bob:password:operator` |
| `NEXUS_SECRET_KEY` | generated | signs sessions and approval links; a weak value is replaced by a random key |
| `NEXUS_SANDBOX_BACKEND` | `docker` | `docker` (isolated, no network) or `local` (subprocess, dev only) |
| `NEXUS_DATABASE_URL` | – | PostgreSQL for app data and checkpoints (`postgresql+asyncpg://…`, `uv sync --extra postgres`); unset = SQLite files |
| `NEXUS_REACT_MODE` | `auto` | worker turns: `native` tool calling, schema-constrained `json`, or `auto` (per model, from the benchmark below) |
| `NEXUS_MISSIONS_PER_MINUTE` / `NEXUS_DAILY_TOKEN_QUOTA` | `10` / `2000000` | per-user limits (`0` quota = no cap) |
| `NEXUS_GOOGLE_CLIENT_ID/SECRET` | – | "Sign in with Google" to send result emails (or paste them in Settings) |

---

## How a mission works

```mermaid
flowchart LR
    U([Prompt]) --> I[intake<br/>guardrails] --> R[rewrite] --> RT{route}
    RT -->|vague| C[clarify<br/>interrupt] --> R
    RT --> P[plan] --> A[assemble team] --> D[dispatch<br/>Send fan-out]
    D --> W1[worker<br/>ReAct] & W2[worker<br/>ReAct] --> CO[collect]
    CO -->|code / answer| T[council<br/>tournament] --> V{validate}
    CO --> S[synthesize] --> V
    V -->|fail| T
    V -->|pass| G{risk gate}
    G -->|LOW| X[execute]
    G -->|MEDIUM / HIGH| H[approval<br/>interrupt] --> X
    X --> VE{verify} -->|unhealthy| RB[rollback] --> P
    VE --> M[memory] --> REP([report])
```

1. **Quill** rewrites the prompt; keyword rules or the fast model **route** it to a playbook.
2. **Sage** writes a typed plan; the **Commander** assigns each step to the best agent by
   reputation and **dispatches** them in parallel with `Send`.
3. Each worker runs a **ReAct** subgraph with its own MCP tool allowlist, using the
   model's **native tool calling** (`tools=[JSON Schema]` → `tool_calls` → `role="tool"`)
   or schema-constrained JSON turns, whichever measured better for the active model.
4. For code and hard questions, **Blaze, Volt and Frost** compete: each patch is tested in a
   sandbox, reviews are anonymous, and the judge **Arbiter** weighs test results most.
5. **Aegis** validates; failures loop back (bounded by guards).
6. A **rule-based risk score** decides: run, ask a human (`interrupt()`), rehearse first, or block.
7. Execute → verify (live traffic for the demo service) → roll back if needed → remember → report.

Every step is checkpointed (SQLite, or PostgreSQL when configured), so missions survive restarts and can be rewound
(Time Travel). Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and the design
decisions in [docs/adr/](docs/adr/).

## Week 4 syllabus coverage

| Day | Topic | Where |
|---|---|---|
| 16 | ReAct · Plan-and-Execute · raw SDK loop with **native tool calling** · conditional routing | `graph/subgraphs/react_worker.py`, `graph/nodes/planning.py`, `llm/raw_react_agent.py` |
| 17 | Typed state · reducers · conditional edges · guarded cycles · `Send` fan-out · subgraphs · `Command` | `graph/state.py`, `graph/reducers.py`, `graph/main_graph.py` |
| 18 | SQLite checkpointing · crash resume · sliding-window and summary pruning · token budgets · long-term memory | `core/runtime.py`, `graph/runner.py`, `memory/` |
| 19 | Supervisor routing · worker delegation · **7 MCP servers** (in-process and **stdio**) | `graph/nodes/work.py`, `mcp_servers/` |
| 20 | `interrupt()` approval gates · email approvals · time travel and forking · guardrails · **RBAC** | `graph/nodes/gate.py`, `hitl/`, `safety/`, `auth/` |

The full map, with the test that proves each item: [docs/TOPIC_COVERAGE.md](docs/TOPIC_COVERAGE.md).

## Security

- **Accounts and roles.** Argon2id password hashes, JWT sessions, login rate limit
  (5 per minute per user and address). One policy table ([auth/policy.py](backend/nexus/auth/policy.py))
  guards every route:

  | Role | Can |
  |---|---|
  | Viewer | read everything |
  | Operator | + start and cancel missions, approve or reject, time travel |
  | Owner | + settings, models, users, chaos switches, agents, deleting missions |

  Signing out revokes the session on the server. Approvals record the signed-in user,
  never a name sent by the client. Public by design:
  health probes, sign-in, signed one-time email-approval links, the Google OAuth callback and
  published pages.
- **Agents are boxed in.** Per-agent MCP tool allowlists, a workspace path jail, a sandbox
  with no network for tests, prompt-injection detection, secret and PII redaction, and
  fencing of untrusted text.
- **Email** goes out only when a prompt asks for it, through Sign in with Google with the
  `gmail.send` scope only (NEXUS never sees the password and cannot read mail).
- **Limits.** Per user: missions per minute and a daily token quota (HTTP 429 with
  `Retry-After`), stored in the database so they survive restarts and are shared by
  replicas; per mission: a token cap.
- **HTTP hardening.** CSP, `nosniff`, frame-deny and a referrer policy on every response;
  published pages may not run scripts.
- **Traceable.** Every response, and every error body, carries an `X-Request-ID`, which is
  also on every log line.
- **Supply chain.** CI runs pip-audit, pnpm audit and CodeQL; Dependabot proposes updates.
- **Secrets** stay in `.env` and `backend/data/` (both ignored by git and Docker).

## Reliability and observability

Model fallback chain (primary → alternate → reduced context), circuit breakers, retries with
jitter, schema-constrained structured output with re-prompts, a per-mission token cap, and a
**Resource Governor** that lowers LLM concurrency under memory pressure instead of crashing.
`GET /metrics` serves Prometheus metrics (missions, tokens, approvals, emails, RAM,
concurrency, queue, tokens/s, circuit breakers); traces and benchmarks are in **Insights**.

## Tests and quality

| Suite | Count | Command |
|---|---|---|
| Backend (pytest; scripted model, real SQLite, MCP, sandbox, demo service, every API route group; 87% line coverage, gate 85%) | 158 | `make test-backend` |
| Same suite on PostgreSQL 16 | 158 | `make test-postgres` |
| Frontend unit and component (vitest, Testing Library) | 28 | `make test-frontend` |
| End-to-end (Playwright; auth on, Simulation provider) | 25 | `make e2e` |
| Lint and types | ruff (incl. blind-except) · mypy --strict · eslint · prettier · tsc strict · 400-line file limit | `make check` |

CI runs all of them on every push, plus pip-audit and pnpm audit
([.github/workflows/ci.yml](.github/workflows/ci.yml)); CodeQL runs separately. `pre-commit
install` adds the fast checks as git hooks.
Live-model tests are marked `@pytest.mark.live`.

**Verified live** on a 16 GB Mac (Balanced profile): every mission type end to end, e.g. a
blog page published in 55 s, a self-heal that fixed a bad tax setting (10/10 tests, 99 live
orders, 0 errors), tickets filed and solved, and email results delivered with an approval
clicked from the email itself.

## Benchmarks

Measured on a 16 GB Mac (M5 Pro), 2026-10-21: the LangGraph ReAct worker, 6 tool tasks with
known numeric answers × 3 runs, each turn format on each model. Reproduce with
`cd backend && uv run python -m nexus.evals.react_modes --runs 3`; raw runs are in
[docs/benchmarks/react_modes.json](docs/benchmarks/react_modes.json).

| Model | Turn format | Correct | Median time | Median tokens | Median LLM calls |
|---|---|---|---|---|---|
| qwen2.5:3b | **native tool calling** | **14/18** | 2.2 s | 1,132 | 2 |
| qwen2.5:3b | JSON turns | 10/18 | 2.7 s | 786 | 2 |
| llama3.2:3b | native tool calling | 13/18 | 2.3 s | 971 | 2 |
| llama3.2:3b | **JSON turns** | **16/18** | 2.7 s | 1,228 | 3 |

What the numbers changed:

- The best format depends on the model, so `NEXUS_REACT_MODE=auto` (the default) uses native
  calls for Qwen and JSON turns for Llama.
- The first run scored 6–8/12. The failures showed the demo calculator rejecting `2^10`
  and giving unhelpful errors. Fixing the tool, not the prompt, lifted every row.
- The remaining misses are mostly the model inventing a fact ("the squad has 10 robots")
  instead of calling `lookup_fact`, a 3B limit that the council and validation stages exist
  to catch.

## Known limitations

- 3B local models sometimes need a second round of work; the guarded fix loops handle it.
- Build API is scoped to small services (8 files or fewer).
- Without Docker the sandbox is a plain subprocess (labelled "not isolated" in the UI).
- Links inside result emails point to the machine running NEXUS.
- PostgreSQL makes the data store and rate limits shareable, but long-term memory (Chroma)
  and the live event bus are per process, so replicas need sticky sessions.

## Repository layout

```
backend/            FastAPI + LangGraph (Python 3.12, uv)
  nexus/graph/      the main graph, nodes, ReAct and tournament subgraphs, runner
  nexus/playbooks/  mission types (web page, self-healing, tickets, builder, council, dynamic)
  nexus/llm/        gateway, router, Ollama provider, raw SDK agent, model profiles
  nexus/mcp_servers/ 7 MCP servers + hub
  nexus/hitl/       approvals, email approvals, time travel, result emails, Google mail
  nexus/auth/       roles, policy table, sessions, rate limit
  nexus/safety/     guardrails, risk scoring, policies
  tests/            pytest suites
frontend/           Next.js 15 + TypeScript (strict), Tailwind v4, Playwright e2e
demo-service/       the FastAPI shop the self-healing missions repair
docs/               architecture, ADRs, topic coverage, mission guide, demo scripts, benchmarks
```

Project: [changelog](CHANGELOG.md) · [contributing](CONTRIBUTING.md) ·
[security policy](SECURITY.md) · [design decisions](docs/adr/).

More: [mission guide](docs/HOW_IT_WORKS.md) · [code walkthrough](docs/CODE_WALKTHROUGH.md) ·
[presentation guide](docs/PRESENTATION_GUIDE.md).

Licence: [MIT](LICENSE).
