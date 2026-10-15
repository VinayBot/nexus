# ADR 0002 — SQLite for checkpoints and app data

**Status:** accepted

## Context
Everything must run on one laptop with no extra services. We need durable checkpoints,
an event log for replay, approvals with an audit trail, and traces.

## Decision
- Two SQLite files: `checkpoints.db` (LangGraph `AsyncSqliteSaver`) and `nexus.db`
  (SQLAlchemy async + aiosqlite, WAL mode, `busy_timeout`).
- The schema is created with `create_all`. There are no migrations: runtime data is
  disposable (`make reset`).

## Consequences
- Zero setup; files can be inspected with any SQLite browser.
- Single-writer limits are fine at laptop scale. WAL keeps readers (UI, WebSocket
  backlog) unblocked.
- Moving to Postgres would mean swapping the saver and the engine URL. There are no
  SQLite-specific queries except `json_extract` in approval history and the upserts.
