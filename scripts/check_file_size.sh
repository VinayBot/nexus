#!/usr/bin/env bash
# Fail when a source file grows past the project's 400-line limit (split it instead).
# Generated files and Alembic migrations are exempt.
set -euo pipefail
cd "$(dirname "$0")/.."
LIMIT=400
over=$(find backend/nexus frontend/src \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' \) \
  -not -path '*/generated/*' -not -path '*/migrations/*' -print0 \
  | xargs -0 wc -l | awk -v max="$LIMIT" '$2 != "total" && $1 > max { print "  " $1 " " $2 }')
if [ -n "$over" ]; then
  echo "Files over $LIMIT lines (split them):"
  echo "$over"
  exit 1
fi
echo "All source files are within $LIMIT lines."
