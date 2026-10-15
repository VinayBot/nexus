#!/usr/bin/env bash
# Fast mode: optimised frontend build (no on-demand compiling) and the backend without
# the file-watching reloader. Same ports as `make dev`. Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
( cd frontend && pnpm build )
# the standalone server needs the static assets next to it
rm -rf frontend/.next/standalone/.next/static frontend/.next/standalone/public
cp -R frontend/.next/static frontend/.next/standalone/.next/static
cp -R frontend/public frontend/.next/standalone/public
trap 'kill 0' EXIT INT TERM
( cd backend && uv run uvicorn nexus.api.app:app --host "${NEXUS_API_HOST:-127.0.0.1}" --port "${NEXUS_API_PORT:-8000}" --log-level warning --no-access-log ) &
( cd frontend/.next/standalone && PORT=3000 HOSTNAME=127.0.0.1 node server.js ) &
wait
