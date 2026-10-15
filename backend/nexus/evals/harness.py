"""Benchmarks: small benchmark suites run against the live local models.

* ``raw_vs_langgraph`` — arithmetic/lookup tasks with known answers through both agents.
* ``council_vs_single`` — questions with reference keywords: one model call vs the council.
* ``pruning`` — a long, fact-laden conversation squeezed into a small budget with each
  strategy, then a question that needs an early fact (retention) and the token saving.

Results are stored in ``eval_runs`` so the UI can chart history across runs.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from nexus.core.logging import get_logger
from nexus.core.services import services
from nexus.db.models import EvalRunRow
from nexus.evals.lab import run_graph, run_raw
from nexus.llm.types import ChatMessage
from nexus.memory.pruning import prune

log = get_logger(__name__)

AGENT_TASKS = [
    ("What is 17 * 23 plus the number of letters in the word 'android'?", "398"),
    ("How many robots are in the default squad, multiplied by 3?", "42"),
    ("What is (144 / 12) to the power of 2, minus 40?", "104"),
]

QA = [
    ("Which HTTP status code means 'Not Found'?", ["404"]),
    (
        "In Python, which keyword defines a generator that yields values lazily: return or yield?",
        ["yield"],
    ),
    (
        "What does the acronym ACID stand for in databases? Name the four properties.",
        ["atomic", "consisten", "isolat", "durab"],
    ),
    (
        "Which data structure gives O(1) average lookup by key: a hash map or a linked list?",
        ["hash"],
    ),
]

FACTS = [
    ("The vault code is", "7319"),
    ("The project's mascot is a", "red panda"),
    ("The release is scheduled for", "March 3rd"),
]


def _hit(answer: str | None, needles: list[str]) -> bool:
    text = (answer or "").lower()
    return all(n.lower() in text for n in needles)


async def suite_raw_vs_langgraph() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    for task, expected in AGENT_TASKS:
        raw = await run_raw(task)
        graph = await run_graph(task)
        cases.append(
            {
                "task": task,
                "expected": expected,
                "raw": {
                    k: raw[k]
                    for k in (
                        "answer",
                        "llm_calls",
                        "prompt_tokens",
                        "completion_tokens",
                        "latency_ms",
                        "retries",
                    )
                }
                | {"correct": expected in str(raw["answer"])},
                "langgraph": {
                    k: graph[k]
                    for k in (
                        "answer",
                        "llm_calls",
                        "prompt_tokens",
                        "completion_tokens",
                        "latency_ms",
                        "retries",
                    )
                }
                | {"correct": expected in str(graph["answer"])},
            }
        )
    summary = {
        side: {
            "accuracy": round(sum(c[side]["correct"] for c in cases) / len(cases), 2),
            "avg_latency_ms": round(sum(c[side]["latency_ms"] for c in cases) / len(cases)),
            "avg_tokens": round(
                sum(c[side]["prompt_tokens"] + c[side]["completion_tokens"] for c in cases)
                / len(cases)
            ),
        }
        for side in ("raw", "langgraph")
    }
    return summary, cases


async def _council_answer(question: str) -> str:
    from nexus.graph.subgraphs.tournament import tournament

    out = await tournament.ainvoke(
        {
            "mission_id": f"eval-{uuid.uuid4().hex[:6]}",
            "playbook": "council_qa",
            "mode": "answer",
            "topic": "eval",
            "question": question,
            "context": "",
            "code_context": None,
            "feedback": "",
            "solvers": ["blaze", "volt", "frost"],
            "critic": "vex",
            "judge_id": "arbiter",
            "proposals": {},
            "scores": {},
            "labels": {},
            "round": 0,
            "max_rounds": 0,
            "threshold": 1.5,
            "reputation": {},
            "verdict": None,
        },
        {"recursion_limit": 60},
    )
    return str(out["proposals"][out["verdict"]["winner"]]["content"])


async def suite_council_vs_single() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    llm = services().llm
    cases: list[dict[str, Any]] = []
    for q, needles in QA:
        t0 = time.perf_counter()
        single = (
            await llm.complete([ChatMessage.user(q)], purpose="solve", stream=False, max_tokens=300)
        ).content
        t1 = time.perf_counter()
        council = await _council_answer(q)
        t2 = time.perf_counter()
        cases.append(
            {
                "question": q,
                "expected": needles,
                "single": {
                    "answer": single[:600],
                    "correct": _hit(single, needles),
                    "latency_ms": round((t1 - t0) * 1000),
                },
                "council": {
                    "answer": council[:600],
                    "correct": _hit(council, needles),
                    "latency_ms": round((t2 - t1) * 1000),
                },
            }
        )
    summary = {
        side: {
            "accuracy": round(sum(c[side]["correct"] for c in cases) / len(cases), 2),
            "avg_latency_ms": round(sum(c[side]["latency_ms"] for c in cases) / len(cases)),
        }
        for side in ("single", "council")
    }
    return summary, cases


def _long_conversation() -> list[ChatMessage]:
    msgs = [ChatMessage.system("You are a helpful assistant. Answer from the conversation.")]
    for i, (lead, fact) in enumerate(FACTS):
        msgs.append(ChatMessage.user(f"Note {i + 1}: {lead} {fact}."))
        msgs.append(ChatMessage.assistant(f"Noted: {lead.lower()} {fact}."))
        for j in range(4):  # filler that pushes the facts out of a small window
            msgs.append(
                ChatMessage.user(
                    f"Unrelated chatter {i}-{j}: " + "the weather is mild and the tea is warm. " * 6
                )
            )
            msgs.append(ChatMessage.assistant("Understood, nothing important there."))
    return msgs


async def suite_pruning() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    llm = services().llm
    budget = 420
    cases: list[dict[str, Any]] = []

    async def summariser(prev: str, old: list[ChatMessage]) -> str:
        text = "\n".join(f"{m.role}: {m.content}" for m in old)
        out = await llm.complete(
            [
                ChatMessage.system(
                    "Summarise into bullet points. Keep every code, name and date exactly."
                ),
                ChatMessage.user(f"Previous summary:\n{prev}\n\nLog:\n{text}"),
            ],
            purpose="summarise",
            stream=False,
            max_tokens=200,
        )
        return out.content

    for strategy in ("sliding_window", "summarise"):
        res = await prune(
            _long_conversation(), budget, agent_id="eval", strategy=strategy, summariser=summariser
        )
        retained = 0
        answers: list[dict[str, Any]] = []
        for lead, fact in FACTS:
            q = [
                *res.messages,
                ChatMessage.user(
                    f"Question: {lead.lower().replace('the ', 'what ', 1)}? Answer with just the value."
                ),
            ]
            ans = (await llm.complete(q, purpose="grade", stream=False, max_tokens=40)).content
            ok = fact.lower().split()[0] in ans.lower()
            retained += ok
            answers.append({"fact": fact, "answer": ans[:120], "retained": ok})
        cases.append(
            {
                "strategy": strategy,
                "before_tokens": res.before,
                "after_tokens": res.after,
                "saved_pct": round(100 * (1 - res.after / max(1, res.before)), 1),
                "retention": round(retained / len(FACTS), 2),
                "answers": answers,
            }
        )
    summary = {
        c["strategy"]: {"retention": c["retention"], "saved_pct": c["saved_pct"]} for c in cases
    }
    return summary, cases


SUITES: dict[
    str, tuple[str, Callable[[], Awaitable[tuple[dict[str, Any], list[dict[str, Any]]]]]]
] = {
    "raw_vs_langgraph": ("Raw SDK agent vs LangGraph agent", suite_raw_vs_langgraph),
    "council_vs_single": ("Council vs single model", suite_council_vs_single),
    "pruning": ("Sliding window vs summarisation pruning", suite_pruning),
}

_running: dict[str, asyncio.Task[None]] = {}


async def start(suite: str) -> str:
    if suite not in SUITES:
        raise KeyError(suite)
    if any(not t.done() for t in _running.values()):
        raise RuntimeError("another eval is running; one at a time keeps the laptop responsive")
    run_id = uuid.uuid4().hex[:10]
    db = services().db
    async with db.session() as s:
        s.add(
            EvalRunRow(
                id=run_id,
                suite=suite,
                status="running",
                model=services().settings.models.main,
                summary={},
                cases=[],
            )
        )

    async def go() -> None:
        try:
            summary, cases = await SUITES[suite][1]()
            status = "completed"
        except Exception as exc:
            log.error("eval.failed", suite=suite, error=str(exc))
            summary, cases, status = {"error": str(exc)}, [], "failed"
        async with db.session() as s:
            row = await s.get(EvalRunRow, run_id)
            if row is not None:
                row.status, row.summary, row.cases, row.finished_at = (
                    status,
                    summary,
                    cases,
                    time.time(),
                )

    _running[run_id] = asyncio.create_task(go(), name=f"eval:{suite}")
    return run_id
