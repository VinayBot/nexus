"""Nova, the in-app guide.

* Knowledge: RAG over the project's own docs (README, docs/, ADRs) in Chroma.
* Live state: a read-only snapshot (missions, pending approvals, recent failures,
  and — when asked about a mission — its current node, robots and verdict).
* UI actions: chosen by deterministic rules, never by the model, and limited to
  safe things — navigate, spotlight, start a tour, start a demo mission.
* Answers stream from the fast model and must separate app knowledge from guesses.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select

from nexus.core.services import services
from nexus.db.models import ApprovalRow, EventRow, GuideMessageRow, MissionRow
from nexus.llm.types import ChatMessage

#: phrase → (route, spotlight element id, label)
ROUTES: list[tuple[str, str, str, str]] = [
    (
        r"time.?travel|rewind|fork|checkpoint",
        "/timetravel",
        "fork-button",
        "Time Travel",
    ),
    (r"approv|approval stamp|email link", "/approvals", "approvals-list", "Approvals"),
    (r"graph|reducer|state inspector|langgraph", "/graph", "live-graph", "Live Graph"),
    (r"arena|council|tournament|solver|judge", "/arena", "arena", "Arena"),
    (
        r"memory|prun|summar|context window|fix library|chroma",
        "/memory",
        "vessels",
        "Memory",
    ),
    (r"agent|registry|roster|reputation|robot", "/agents", "agents", "Agents"),
    (r"mcp|tool|sandbox", "/tools", "tools-grid", "Tools"),
    (r"chaos|switch|incident|self.?heal|demo.?service", "/chaos", "chaos-switches", "Chaos Lab"),
    (r"trace|token usage|observ|latency|retries|circuit", "/insights", "traces", "Observatory"),
    (r"eval|benchmark|proving", "/insights?tab=benchmarks", "suites", "Benchmarks"),
    (
        r"architecture|how .* built|components",
        "/learn",
        "architecture",
        "Architecture Explorer",
    ),
    (
        r"curriculum|topic|day 1[6-9]|day 20|week.?4",
        "/learn?tab=curriculum",
        "curriculum",
        "Curriculum Map",
    ),
    (
        r"raw sdk|under the hood|without (a )?framework",
        "/insights?tab=lab",
        "lab",
        "Under the Hood",
    ),
    (r"setting|model|concurrency|polic", "/settings", "settings", "Settings"),
    (
        r"mission control|command center floor|thought stream",
        "/missions",
        "mission-floor",
        "Mission Control",
    ),
]
PER_MISSION = {"/timetravel", "/graph", "/arena"}

SUGGESTIONS = [
    "Give me the guided tour",
    "What is happening right now?",
    "Show me time travel",
    "Explain reducers using this mission",
    "Why did the Judge pick the winner?",
    "Start a demo mission",
]


def actions_for(question: str, mission_id: str | None) -> list[dict[str, Any]]:
    q = question.lower()
    if re.search(r"\btour\b|walk me through|presentation", q):
        return [{"type": "tour", "tour": "main", "label": "Start the guided tour"}]
    if re.search(r"start (a )?demo|run (a )?demo|try a mission", q):
        return [{"type": "start_demo", "label": "Start a Council Q&A demo mission"}]
    if not re.search(r"show|open|take me|go to|where|navigate", q):
        return []
    for pattern, route, element, label in ROUTES:
        if re.search(pattern, q):
            path = f"{route}/{mission_id}" if route in PER_MISSION and mission_id else route
            return [
                {"type": "navigate", "path": path, "label": f"Open {label}"},
                {"type": "spotlight", "element": element},
            ]
    return []


async def live_snapshot(mission_id: str | None) -> str:
    db = services().db
    lines: list[str] = []
    async with db.session() as s:
        active = (
            (
                await s.execute(
                    select(MissionRow).where(MissionRow.status.in_(["running", "paused"])).limit(5)
                )
            )
            .scalars()
            .all()
        )
        pending = (
            (await s.execute(select(ApprovalRow).where(ApprovalRow.status == "pending").limit(5)))
            .scalars()
            .all()
        )
        failed = (
            (
                await s.execute(
                    select(MissionRow)
                    .where(MissionRow.status == "failed")
                    .order_by(MissionRow.updated_at.desc())
                    .limit(2)
                )
            )
            .scalars()
            .all()
        )
        lines.append(
            f"Active missions: {len(active)}"
            + "".join(f"\n- {m.id} [{m.status}] {m.title} ({m.playbook})" for m in active)
        )
        lines.append(
            f"Pending approvals: {len(pending)}"
            + "".join(f"\n- {a.kind}: {a.payload.get('summary', '')}" for a in pending)
        )
        for m in failed:
            lines.append(f"Recently failed: {m.title} — {(m.error or '')[:160]}")
        if mission_id:
            m = await s.get(MissionRow, mission_id)
            evs = (
                (
                    await s.execute(
                        select(EventRow)
                        .where(EventRow.mission_id == mission_id)
                        .order_by(EventRow.seq.desc())
                        .limit(80)
                    )
                )
                .scalars()
                .all()
            )
            if m:
                lines.append(
                    f"Focused mission {m.id}: {m.title} — status {m.status}, outcome {m.outcome}, playbook {m.playbook}"
                )
            node = next((e.payload["node"] for e in evs if e.type == "node.entered"), None)
            if node:
                lines.append(f"Current/last graph node: {node}")
            seen: set[str] = set()
            for e in evs:
                agent = e.payload.get("agent_id") if isinstance(e.payload, dict) else None
                if e.type == "agent.status" and agent and agent not in seen:
                    seen.add(agent)
                    lines.append(f"Robot {agent}: {e.payload['status']}")
                if e.type == "agent.thinking" and agent and f"t:{agent}" not in seen:
                    seen.add(f"t:{agent}")
                    lines.append(f"{agent} last thought: {e.payload['text'][:160]}")
            verdict = next((e.payload for e in evs if e.type == "council.verdict"), None)
            if verdict:
                lines.append(
                    f"Latest verdict: {verdict['winner_label']} ({verdict['winner']}) confidence {verdict['confidence']}; dissent: {verdict['dissent'][:200]}"
                )
            merges = [e.payload for e in evs if e.type == "reducer.merged"][:6]
            if merges:
                lines.append(
                    "Recent reducer merges: "
                    + "; ".join(
                        f"{p['channel']} via {p['reducer']} +{p['added']}→{p['total']}"
                        for p in merges
                    )
                )
    return "\n".join(lines)


async def answer(
    question: str, conversation_id: str, mission_id: str | None
) -> AsyncIterator[dict[str, Any]]:
    svc = services()
    acts = actions_for(question, mission_id)
    yield {"type": "actions", "actions": acts}
    memory = svc.extras.get("memory")
    hits: list[dict[str, Any]] = []
    if memory is not None:
        try:
            hits = await memory.search(question, ["docs"], k=4, emit_event=False)
        except Exception:
            hits = []
    docs = "\n\n".join(f"[{h['title']}]\n{h['text'][:700]}" for h in hits) or "(no matching docs)"
    state = await live_snapshot(mission_id)
    async with svc.db.session() as s:
        history = (
            (
                await s.execute(
                    select(GuideMessageRow)
                    .where(GuideMessageRow.conversation_id == conversation_id)
                    .order_by(GuideMessageRow.id.desc())
                    .limit(6)
                )
            )
            .scalars()
            .all()
        )
        s.add(
            GuideMessageRow(
                conversation_id=conversation_id, role="user", content=question, actions=[]
            )
        )
    msgs = [
        ChatMessage.system(
            svc.registry.get("nova").system_prompt
            + "\nAnswer in at most 6 short sentences, friendly and precise. Use the DOCS for how NEXUS "
            "works and LIVE STATE for what is happening now. If something is not in either, say it is a "
            "guess or that you do not know. Never claim you performed an action; the UI performs "
            "navigation separately."
        ),
        *[
            ChatMessage(role="assistant" if m.role == "assistant" else "user", content=m.content)
            for m in reversed(history)
        ],
        ChatMessage.user(f"DOCS:\n{docs}\n\nLIVE STATE:\n{state}\n\nQUESTION: {question}"),
    ]
    tokens: list[str] = []
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def on_token(piece: str) -> None:
        await queue.put(piece)

    async def run() -> None:
        try:
            await svc.llm.complete(
                msgs,
                purpose="guide",
                agent_id=None,
                max_tokens=320,
                temperature=0.3,
                stream=True,
                on_token=on_token,
            )
        except Exception as exc:
            await queue.put(f"\n\n(I could not reach the local model: {exc})")
        finally:
            await queue.put(None)

    task = asyncio.create_task(run())
    while (piece := await queue.get()) is not None:
        tokens.append(piece)
        yield {"type": "token", "text": piece}
    await task
    text = "".join(tokens)
    async with svc.db.session() as s:
        s.add(
            GuideMessageRow(
                conversation_id=conversation_id, role="assistant", content=text, actions=acts
            )
        )
    yield {"type": "done", "sources": [h["title"] for h in hits], "used_live_state": bool(state)}
