#!/usr/bin/env bash
# Recommended Ollama server settings for a 16 GB Apple Silicon Mac.
# Usage:  source scripts/ollama_env.sh && ollama serve
# (If Ollama runs as the menu-bar app, set these with `launchctl setenv NAME value` and restart it.)
export OLLAMA_NUM_PARALLEL=2        # parallel requests per loaded model (shares one copy of the weights)
export OLLAMA_MAX_LOADED_MODELS=2   # main + fast; embeddings model is tiny
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0    # halves KV-cache memory vs f16
export OLLAMA_KEEP_ALIVE=30m
echo "Ollama env: parallel=$OLLAMA_NUM_PARALLEL max_loaded=$OLLAMA_MAX_LOADED_MODELS kv=$OLLAMA_KV_CACHE_TYPE"
