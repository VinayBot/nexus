#!/usr/bin/env bash
# Pull the models for the configured profile (reads NEXUS_* from .env if present).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
profile="${NEXUS_MODEL_PROFILE:-lite}"
case "$profile" in
  lite)     main=llama3.2:3b;      fast=llama3.2:3b ;;
  standard) main=qwen2.5-coder:7b; fast=llama3.2:3b ;;
  *) echo "unknown profile: $profile" >&2; exit 1 ;;
esac
main="${NEXUS_MODEL_MAIN:-$main}"; fast="${NEXUS_MODEL_FAST:-$fast}"; embed="${NEXUS_MODEL_EMBED:-nomic-embed-text}"
command -v ollama >/dev/null || { echo "Install Ollama first: https://ollama.com/download" >&2; exit 1; }
for m in $(printf '%s\n' "$main" "$fast" "$embed" | sort -u); do
  if ollama list | awk 'NR>1{print $1}' | grep -qx -e "$m" -e "$m:latest"; then echo "✓ $m"; else echo "↓ $m"; ollama pull "$m"; fi
done
