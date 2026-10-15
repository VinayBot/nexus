#!/usr/bin/env bash
# Start backend (uvicorn --reload) and frontend (next dev) together; Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
trap 'kill 0' EXIT INT TERM
( cd backend && uv run uvicorn nexus.api.app:app --host "${NEXUS_API_HOST:-127.0.0.1}" --port "${NEXUS_API_PORT:-8000}" --reload --reload-dir nexus ) &
( cd frontend && pnpm dev ) &
wait
