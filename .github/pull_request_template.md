## What and why

<!-- One or two sentences. Link the issue: Closes #123 -->

## How it was tested

- [ ] `make check` (lint, mypy --strict, backend + frontend tests)
- [ ] `make e2e` (for UI changes)
- [ ] `make test-postgres` (for database changes)
- [ ] Live run on Ollama (for agent or prompt changes): which mission, which model

## Checklist

- [ ] Migration added for schema changes (`alembic revision --autogenerate`)
- [ ] New routes covered by `auth/policy.py` and a test
- [ ] Untrusted text is fenced; no secrets in code or logs
- [ ] Docs and `CHANGELOG.md` updated
