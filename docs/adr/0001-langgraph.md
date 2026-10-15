# ADR 0001 — LangGraph for orchestration

**Status:** accepted

## Context
The brief asks for multi-agent orchestration with retries, persistence and human
approval gates. We need typed state, cycles, parallel fan-out, interrupts, and
checkpoint-level time travel.

## Decision
Use LangGraph 1.x (`StateGraph`, `Send`, `Command`, `interrupt`, `RetryPolicy`,
`AsyncSqliteSaver`). One compiled orchestrator graph serves every playbook. Playbooks
plug in through hooks (plan template, validate, execute, verify, rollback) instead of
each owning a graph.

## Consequences
- One graph to inspect, render and test. The Live Graph shows the real compiled structure.
- Interrupts and `update_state` give approvals and forks almost for free.
- Some nodes do nothing for some playbooks (e.g. `verify` for Council Q&A), which is
  visible but harmless.
- Subgraphs are compiled with `checkpointer=False`. A crash mid-subgraph re-runs that
  super-step, but finished parallel tasks are not re-run (pending writes).
