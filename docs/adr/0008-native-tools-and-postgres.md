# ADR 0008: Native tool calling in workers, optional PostgreSQL

**Status:** accepted (2026-10-21)

## Context

The ReAct workers used schema-constrained JSON turns (`format=<schema>`) because early
3B models were unreliable at native tool calling. The Week 2 review asked for provider
native tool calling, and named SQLite as a scalability limit.

## Decision

**Native tool calling is a first-class turn format** (`NEXUS_REACT_MODE=native`). Tools go
out as JSON Schema, the model answers with structured `tool_calls`, and results come back
as `role="tool"` messages. Small models still slip, so three safety nets stay in place:

1. a call written as text, either JSON (`{"name": …, "arguments": …}` or a ReAct turn) or
   Python style (`tool(arg="x")`, typical of llama3.2:3b), is recovered and executed,
   unless it only quotes a call already made;
2. an empty reply falls back to one schema-constrained JSON turn;
3. `NEXUS_REACT_MODE=json` switches every turn back to the JSON protocol.

A measured benchmark (`python -m nexus.evals.react_modes`, 6 tool tasks × 3 runs, results in
`docs/benchmarks/react_modes.json`) showed the better format depends on the model:
qwen2.5:3b scored 14/18 native vs 10/18 JSON, llama3.2:3b 16/18 JSON vs 13/18 native. So the
default is `auto`: native for Qwen-family models, JSON turns for Llama, decided from the
model active on the router (Settings → Models can switch it at runtime).

**PostgreSQL is optional** (`NEXUS_DATABASE_URL=postgresql+asyncpg://…`,
`uv sync --extra postgres`). App data uses a pooled asyncpg engine with dialect-aware
upserts and portable JSON path queries; LangGraph checkpoints use `AsyncPostgresSaver`.
SQLite stays the default, because a local-first app should start with zero setup.

## Consequences

- The same backend can run as several replicas behind one database. Long-term memory
  (Chroma) and the in-process rate limiters remain per node.
- CI runs the whole suite twice, on SQLite and on PostgreSQL 16, so neither path rots.
- Writing the Postgres path found two real bugs: a SQLite-only `json_extract` query, and
  the stdio MCP server reusing pooled connections across event loops.
