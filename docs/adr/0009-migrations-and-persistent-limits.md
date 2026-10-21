# ADR 0009: Schema migrations, persistent rate limits, revocable sessions

**Status:** accepted (2026-10-21)

## Context

The schema was created with `create_all` (ADR 0002), so a model change could not reach an
existing database safely. Rate limits lived in process memory: they reset on restart and
were not shared between replicas (a point from the Week 2 review). Signing out only
forgot the token in the browser, so a copied token stayed valid until it expired.

## Decision

- **Alembic** owns the schema (`backend/nexus/db/migrations`). The app runs
  `alembic upgrade head` on startup for SQLite and PostgreSQL alike. A database created by
  an older `create_all` is stamped at the baseline (`0001`) and then upgraded, keeping its
  data. A test fails if the models and the migrations drift apart.
- **Rate limits are rows** (`rate_hits`, a sliding window per key). They survive restarts,
  and every replica on the same PostgreSQL shares them. Old hits are pruned on access.
- **Sessions carry a `jti`.** `POST /auth/logout` stores it in `revoked_tokens` until the
  token would expire anyway; the guard rejects revoked ids on every request.

## Consequences

- One extra indexed lookup per authenticated request, and three small queries per
  rate-limited call. Both are negligible next to model latency.
- Two replicas racing on one key can overshoot a limit by one request. This is acceptable
  for abuse limits.
- New schema changes need `uv run alembic revision --autogenerate -m "…"` (see
  CONTRIBUTING.md).
