# ADR 0003 — Parallel agents share one loaded model

**Status:** accepted

## Context
The owner's 16 GB Mac has crashed under larger models. Running one model per parallel
agent would multiply memory use.

## Decision
- Parallel workers and tournament solvers share the same Ollama model and differ by
  persona, system prompt, strategy and temperature.
- `OLLAMA_NUM_PARALLEL` serves concurrent requests from one copy of the weights.
- The Resource Governor caps concurrent calls and lowers the cap under memory pressure.
  Work queues instead of failing.
- The default `lite` profile uses llama3.2:3b for every role (about 2.5 GB resident).
  The `standard` profile (qwen2.5-coder:7b main) is opt-in.

## Consequences
- Memory stays flat no matter how many agents run.
- Agents share the model's blind spots. This is why tournaments are grounded in tests
  (ADR 0004).
