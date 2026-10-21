# NEXUS — common tasks. Run `make help` for the list.
SHELL := /bin/bash
export COREPACK_ENABLE_DOWNLOAD_PROMPT := 0
COMPOSE := $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo docker-compose)

.PHONY: help setup models dev prod backend frontend test test-backend test-postgres audit test-frontend lint typecheck e2e \
        types sandbox-image mail demo reset check

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[33m%-14s\033[0m %s\n",$$1,$$2}'

setup: ## Install backend (uv) and frontend (pnpm) dependencies; create .env
	@[ -f .env ] || cp .env.example .env
	cd backend && uv sync
	corepack enable pnpm >/dev/null 2>&1 || true
	cd frontend && pnpm install
	cd frontend && pnpm exec playwright install chromium >/dev/null 2>&1 || true

models: ## Pull the Ollama models for the configured profile
	./scripts/pull_models.sh

dev: ## Run backend :8000 and frontend :3000 together
	./scripts/dev.sh

prod: ## Fast mode: optimised frontend build + backend without the reloader
	./scripts/prod.sh

backend: ## Run only the backend
	cd backend && uv run uvicorn nexus.api.app:app --reload --reload-dir nexus --port 8000

frontend: ## Run only the frontend
	cd frontend && pnpm dev

mail: ## Start Mailpit (email capture UI on http://localhost:8025)
	$(COMPOSE) up -d mailpit

sandbox-image: ## Build the isolated test-runner image used by sandbox-exec
	docker build -t nexus-sandbox:latest sandbox

test: test-backend test-frontend ## Run all offline tests

test-backend:
	cd backend && uv run pytest -q --cov=nexus --cov-report=term:skip-covered --cov-fail-under=80

test-postgres: ## Backend tests against a throwaway PostgreSQL 16 container
	docker run -d --rm --name nexus-test-pg -e POSTGRES_USER=nexus -e POSTGRES_PASSWORD=nexus \
		-e POSTGRES_DB=nexus -p 55432:5432 postgres:16-alpine >/dev/null
	until docker exec nexus-test-pg pg_isready -U nexus >/dev/null 2>&1; do sleep 1; done
	cd backend && uv sync --extra postgres -q && \
		NEXUS_TEST_DATABASE_URL=postgresql+asyncpg://nexus:nexus@127.0.0.1:55432/nexus uv run pytest -q; \
		status=$$?; docker stop nexus-test-pg >/dev/null; exit $$status

audit: ## Known-vulnerability scan of Python and npm dependencies
	cd backend && uv export --frozen --no-dev --extra postgres --no-hashes --no-emit-project -o /tmp/nexus-req.txt && \
		uv run pip-audit -r /tmp/nexus-req.txt --no-deps --disable-pip \
		--ignore-vuln PYSEC-2026-311 --ignore-vuln PYSEC-2026-3813 \
		--ignore-vuln PYSEC-2026-3814 --ignore-vuln PYSEC-2026-3815
	cd frontend && pnpm audit --prod

test-frontend:
	cd frontend && pnpm test

lint: ## Ruff + ESLint + Prettier check
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && pnpm lint && pnpm format:check

typecheck: ## mypy (strict) + tsc
	cd backend && uv run mypy
	cd frontend && pnpm typecheck

check: lint typecheck test ## Everything CI runs

e2e: ## Playwright end-to-end tests (starts both servers)
	cd frontend && pnpm e2e

types: ## Regenerate frontend event types from the backend's JSON Schema
	cd backend && uv run python -m nexus.core.export_schema > ../frontend/src/lib/generated/events.schema.json
	cd frontend && pnpm gen:types

demo: ## Seed demo data (tickets, docs, fix library) for the walkthrough
	python3 scripts/seed_demo.py

reset: ## Delete all runtime data (SQLite, Chroma, workspaces)
	rm -rf backend/data
	@echo "runtime data removed"
