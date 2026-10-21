# Contributing

## Workflow

1. Branch from `main`: `feat/<topic>`, `fix/<topic>` or `docs/<topic>`.
2. Keep commits small, with [Conventional Commit](https://www.conventionalcommits.org)
   messages (`feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `test:`).
3. Run `make check` (and `make e2e` for UI changes) before you push. `pre-commit install`
   runs the fast checks on every commit.
4. Open a pull request using the template. CI must be green: lint, `mypy --strict`, the
   backend suite on SQLite and PostgreSQL with the coverage gate, the frontend checks,
   Playwright, the dependency audits and CodeQL.
5. Add an entry to [CHANGELOG.md](CHANGELOG.md) under "Unreleased".

## Rules of the codebase

- Model names live only in `backend/nexus/core/config.py` (profiles).
- Every agent input and output is a Pydantic model; untrusted text goes through
  `safety.guardrails.fence()`.
- A schema change needs a migration:
  `cd backend && uv run alembic revision --autogenerate -m "what changed"`. The
  `test_migrations_build_exactly_the_model_schema` test fails if you forget.
- A new API route is protected by default (reads need viewer, writes need operator). Add an
  explicit rule to `auth/policy.py` only when it needs something else.
- Live UI animations come from real backend events; scripted motion only in Replay and
  Simulation mode.
- Tests use the deterministic `ScriptedLLM`; mark tests that need Ollama `@pytest.mark.live`.
- Files stay under about 400 lines; split instead.

## Releasing

Update `CHANGELOG.md`, bump the version in `backend/pyproject.toml` and
`frontend/package.json`, tag `vX.Y.Z` on `main`, and push the tag.
