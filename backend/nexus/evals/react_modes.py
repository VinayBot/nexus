"""Benchmark: the LangGraph ReAct worker with native tool calling vs schema-constrained
JSON turns, on the local models. Every task has a known numeric answer that needs tools.

    uv run python -m nexus.evals.react_modes            # needs Ollama on :11434
    uv run python -m nexus.evals.react_modes --runs 2 --models qwen2.5:3b

Writes ``docs/benchmarks/react_modes.json`` and prints a Markdown table.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from nexus.agents.toolbox import LocalToolBox
from nexus.core.config import get_settings
from nexus.core.events import Event, bus
from nexus.llm.demo_tools import TOOL_FNS, TOOL_SPECS

TASKS = [
    ("What is 17 * 23 plus the number of letters in the word 'android'?", "398"),
    ("How many robots are in the default squad, multiplied by 3?", "42"),
    ("What is (144 / 12) to the power of 2, minus 40?", "104"),
    ("How many letters are in the word 'orchestration', times 4?", "52"),
    ("What is 365 * 24?", "8760"),
    ("What is 2 to the power of 10, minus the number of letters in 'langgraph'?", "1015"),
]
TOOLS = [f"demo.{s.name}" for s in TOOL_SPECS]
OUT = Path(__file__).resolve().parents[3] / "docs" / "benchmarks" / "react_modes.json"


def toolbox() -> LocalToolBox:
    return LocalToolBox(
        {
            f"demo.{s.name}": (s.model_copy(update={"name": f"demo.{s.name}"}), TOOL_FNS[s.name])
            for s in TOOL_SPECS
        }
    )


async def run_one(task: str, expected: str) -> dict[str, Any]:
    from nexus.core.services import services
    from nexus.graph.subgraphs.react_worker import initial_worker_state, react_worker

    events: list[Event] = []
    bus.reset()
    bus.add_listener(events.append)
    spec = services().registry.get("echo")
    started = time.perf_counter()
    try:
        out = await asyncio.wait_for(
            react_worker.ainvoke(initial_worker_state(spec, task, TOOLS)), 180
        )
        answer = str(out.get("final") or "")
    except Exception as exc:  # noqa: BLE001 - a failed run counts as wrong, the benchmark goes on
        answer = f"error: {exc!r}"
    calls = [e.payload for e in events if e.type == "llm.call"]
    return {
        "task": task,
        "ok": expected in answer.replace(",", ""),
        "seconds": round(time.perf_counter() - started, 2),
        "llm_calls": len(calls),
        "tokens": sum(c["prompt_tokens"] + c["completion_tokens"] for c in calls),
        "tool_calls": sum(1 for e in events if e.type == "agent.action"),
        "answer": answer[:200],
    }


async def run_config(model: str, mode: str, runs: int) -> list[dict[str, Any]]:
    from nexus.core.runtime import runtime
    from nexus.llm.ollama_provider import OllamaProvider

    os.environ.update(NEXUS_MODEL_MAIN=model, NEXUS_REACT_MODE=mode)
    get_settings.cache_clear()
    rows = []
    provider = OllamaProvider("http://127.0.0.1:11434")
    async with runtime(
        get_settings(), provider=provider, toolbox=toolbox(), recover=False, memory=False
    ):
        for _ in range(runs):
            for task, expected in TASKS:
                rows.append(await run_one(task, expected))
    return rows


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "accuracy": f"{sum(r['ok'] for r in rows)}/{len(rows)}",
        "median_s": round(statistics.median(r["seconds"] for r in rows), 1),
        "median_tokens": int(statistics.median(r["tokens"] for r in rows)),
        "median_llm_calls": statistics.median(r["llm_calls"] for r in rows),
    }


async def main(models: list[str], runs: int) -> None:
    with tempfile.TemporaryDirectory() as tmp:  # never touch the real data directory
        os.environ.update(
            NEXUS_DATA_DIR=tmp,
            NEXUS_ENV="test",
            NEXUS_AUTH_ENABLED="false",
            NEXUS_DEMO_AUTOSTART="false",
            NEXUS_OLLAMA_BASE_URL="http://127.0.0.1:11434",
            NEXUS_LOG_LEVEL="ERROR",
        )
        results: dict[str, Any] = {}
        for model in models:
            for mode in ("native", "json"):
                rows = await run_config(model, mode, runs)
                results[f"{model}|{mode}"] = {"summary": summarise(rows), "runs": rows}
                print(model, mode, results[f"{model}|{mode}"]["summary"], flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps({"measured_at": time.strftime("%Y-%m-%d"), "results": results}, indent=2)
    )
    print("\n| Model | Turn format | Correct | Median time | Median tokens | Median LLM calls |")
    print("|---|---|---|---|---|---|")
    for key, value in results.items():
        model, mode = key.split("|")
        s = value["summary"]
        print(
            f"| {model} | {mode} | {s['accuracy']} | {s['median_s']} s | "
            f"{s['median_tokens']:,} | {s['median_llm_calls']} |"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=["qwen2.5:3b", "llama3.2:3b"])
    parser.add_argument("--runs", type=int, default=2)
    args = parser.parse_args()
    asyncio.run(main(args.models, args.runs))
