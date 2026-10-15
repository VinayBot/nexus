# Topic coverage (Week 4, Days 16–20)

Each concept: where it is implemented (paths under `backend/nexus/` unless noted), the
test that proves it, and where to see it in the UI. The in-app **Curriculum Map**
(`/curriculum`) shows the same table, plus live counts of the events that prove each
concept ran on this machine.

## Day 16 — Multi-Agent Systems

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| ReAct (Reason–Act–Observe) | `graph/subgraphs/react_worker.py` — `think` ⇄ `act`, `finalize` on the iteration guard | `test_graph_missions.py::test_react_iteration_guard_forces_final`, `::test_council_qa_runs_end_to_end` | Mission Control → Thought Stream (Thought / Action / Observation chips) |
| Plan-and-Execute | `graph/nodes/planning.py::plan` (typed `Plan`, replanner revisions), `graph/nodes/work.py::dispatch` (executes ready steps by dependency) | `test_validation_failures_hit_fix_and_replan_guards`, `test_playbooks.py::test_project_builder_builds_tests_and_packages` (dependency waves) | Live Graph (`plan`, `dispatch` ×N); Thought Stream "Plan r0/r1" |
| Raw SDK agent (no framework) | `llm/raw_react_agent.py` (httpx only: manual prompt, parsing, loop, retries) | `test_raw_agent.py` (+ `@live` against Ollama) | Under the Hood; Proving Grounds "Raw SDK vs LangGraph" |
| Conditional routing | `graph/nodes/understand.py::route/after_route`; `after_validate`, `after_gate`, `after_approval`, `after_verify`, `after_rollback` | `test_router_picks_playbook_and_emits_edge`, `test_hitl.py` (risk routes) | Live Graph — the chosen branch label flashes on the edge |

## Day 17 — LangGraph core: states & cycles

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| State machine, typed state | `graph/state.py::MissionState`, `graph/main_graph.py::build_graph` (20 nodes) | all graph tests | Live Graph + State Inspector |
| Reducers | `graph/reducers.py` — `merge_dict`, `merge_scores`, `dedupe_append`, `sum_counts`, `append_list`, `add_messages` | `test_units_core.py` reducer tests; parallel fan-in asserted in `test_council_qa_runs_end_to_end` | State Inspector "Reducer merges" (which reducer merged what, live) |
| Conditional edges | `add_conditional_edges` for route, assemble, collect, validate, risk gate, approval, execute, verify, rollback | as above | Live Graph (dashed edges = conditional) |
| Cycles with guards | `state.DEFAULT_LIMITS` (clarify, dispatch, fix, replan, verify, debate, react), counters in `state.loops` (`sum_counts`) | `test_validation_failures_hit_fix_and_replan_guards`, `test_react_iteration_guard_forces_final`, `test_self_healing.py::test_failed_verification_rolls_back` | Live Graph ×N iteration badges; Stage strip counters |
| Parallel fan-out / fan-in | `dispatch` returns `Command(goto=[Send("worker", …)])`; `collect` is the fan-in; the tournament uses `Send` for solvers and reviewers | `test_council_qa_runs_end_to_end` (2 workers, 3 solvers, 3 reviews each) | Dojo Floor (scrolls fly to several workers at once, "Send ×N") |
| Subgraphs | `react_worker`, `tournament` (compiled graphs invoked by nodes; structures exported to the UI) | graph tests | Live Graph (worker/council marked as subgraphs) |
| Command handoffs | `dispatch` → `Command(goto=…, update=…)` | graph tests | Thought Stream "Handoff shogun → agent" |

## Day 18 — Memory systems & context pruning

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| SQLite persistence | `AsyncSqliteSaver` in `core/runtime.py`; app tables in `db/models.py` | `test_crashed_mission_resumes_from_sqlite_checkpoint` | Scroll of Time; checkpoint seals in Mission Control |
| Crash resume | `graph/runner.py::recover()` on startup; shutdown keeps missions "running" | same test (planning is not redone after restart); also verified live when a dev reload restarted the backend mid-mission | "Mission resumed from checkpoint" in the Thought Stream |
| Sliding-window pruning | `memory/pruning.py::sliding_window` (system + pinned + recent) | `test_sliding_window_keeps_system_pinned_and_recent` | Memory Palace (vessels, pruning events) |
| Summarisation pruning | `memory/pruning.py::summarise` (rolling pinned summary, fallback to the window) | `test_summarise_folds_old_turns_into_pinned_summary`, `test_summarise_failure_falls_back_to_sliding_window` | Memory Palace; Proving Grounds "pruning" suite |
| Token limits / budgets | `llm/tokens.py` (estimates calibrated against Ollama's `prompt_eval_count`, `TokenBudget`), `core/meter.py` (per-mission cap from policy) | `test_token_estimates_learn_from_real_counts`, `test_budget_window_and_record`; the cap stopped a real mission at 124,576 / 120,000 tokens | Observatory; State Inspector token bars |
| Long-term memory | `memory/long_term.py` (Chroma: `fix_library`, `missions`, `docs`, `lessons`; PCA map) | `test_mcp.py::test_knowledge_search`, `test_self_healing_end_to_end` (Fix Library write) | Memory Palace library, search and embedding map |

## Day 19 — Multi-agent workflows & MCP

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| Supervisor routing | `planning.py::assemble` (reputation-aware team), `work.py::dispatch` (the Shogun hands off steps) | graph tests | Dojo Floor (Shogun on the dais) |
| Worker delegation | `work.py::worker` → ReAct subgraph per step with a per-agent tool allowlist | graph tests | Thought Stream; Barracks (allowlists) |
| Custom MCP servers | `mcp_servers/` — workspace (path jail), sandbox, knowledge, tickets (+GitHub), notify (system-only), observability, demo; `hub.py` | `test_mcp.py` (all servers, path jail, allowlist, notify guard, sandbox, tickets) | Armory (servers, tools, schemas, health, call log, "try tool") |

## Day 20 — Human-in-the-loop & safety

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| State interrupts | `interrupt()` in `clarify`, `assemble` (team), `approval`; resumed with `Command(resume=…)` in `runner.resume` | `test_vague_task_interrupts_for_clarification_then_resumes`, `test_dynamic_mission_requires_team_approval…` | Shogun's Seal; "Awaiting your seal" in Mission Control |
| Approval gates | `safety/risk.py` + `policies.yaml` route to approval; `hitl/approvals.py` | `test_hitl.py` (approve, reject, CRITICAL override) | Shogun's Seal (risk gauge, hanko stamp) |
| E-mail approvals | `hitl/tokens.py` (signed, expiring, single-use), `hitl/email_approvals.py` (GET confirm, POST decide), Mailpit | `test_approval_email_link_resumes_mission_and_is_single_use`, `test_tampered_and_expired_tokens_are_rejected` | Mailpit inbox; e-mail status chip on approval cards |
| Time travel | `hitl/timetravel.py` — history tree, `state_at`, re-run, fork via `update_state`, choose runner-up, compare | `test_time_travel_runner_up_fork_and_compare`, `test_fork_with_state_patch_reruns_from_checkpoint`; e2e `timetravel.spec.ts` | Scroll of Time |
| Safety | guardrails (injection, redaction, fencing), allowlists, path jail, sandbox, policies, audit log | `test_units_core.py` guardrail and risk tests; `test_ticket_injection_is_flagged` | Settings → Policies; Audit log tab |

## Brief — reliability with local open models

| Concept | Implementation | Tests | UI |
|---|---|---|---|
| Automated retries | transport (`reliability/retry.py`, tenacity, jitter, events), node (`RetryPolicy`), validation re-prompts (`gateway.structured`), JSON repair | `test_reliability.py`, `test_llm_gateway.py` | Robots go dizzy with an ×N badge; Observatory "retries absorbed" |
| Fallbacks | primary → alternate model → reduced context (`gateway.complete`); safe defaults; dead letters with "retry from here" | `test_fallback_chain_alternate_model_then_reduced_context` | Observatory |
| Circuit breakers | `reliability/circuit_breaker.py` per model | `test_circuit_breaker_*`, `test_all_fallbacks_failing_raises_and_opens_circuit` | Observatory circuit list |
| Local open models | Ollama provider, model router (fast/main), Resource Governor | `test_router_*`, governor tests | Dojo Power gauge; Settings |
