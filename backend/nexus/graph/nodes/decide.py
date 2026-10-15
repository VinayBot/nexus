"""Council tournament node and validator (test → fix → test loop, then replan)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage

from nexus.agents import reputation
from nexus.agents.reputation import agent_stats
from nexus.core.event_types import CouncilProposal
from nexus.core.events import emit
from nexus.graph.nodes.common import count, limit, note, status, take
from nexus.graph.schemas import EvidenceItem, Verdict
from nexus.graph.subgraphs.tournament import tournament
from nexus.playbooks import get_playbook


def _reputation_scores(
    stats: dict[str, dict[str, Any]], solvers: list[str], topic: str
) -> dict[str, float]:
    """0-10 scale; 5 = unknown. Topic wins count most."""
    out: dict[str, float] = {}
    for sid in solvers:
        s = stats.get(sid) or {}
        out[sid] = min(
            10.0,
            5.0
            + float((s.get("topics") or {}).get(topic, 0)) * 0.5
            + float(s.get("wins", 0)) * 0.1,
        )
    return out


async def council(state: dict[str, Any]) -> dict[str, Any]:
    playbook = get_playbook(state["playbook"])
    brief = playbook.tournament_brief(state)
    feedback = ""
    validation = state.get("validation") or {}
    if validation and not validation.get("ok"):
        feedback = f"{validation.get('summary', '')}\n{validation.get('details', '')}".strip()
    for sid in brief.solvers:
        status(sid, "walking")
    for sid, seed in brief.seed_proposals.items():
        emit(
            "council.proposal",
            CouncilProposal(
                solver_id=sid,
                strategy=seed.get("strategy", "memory"),
                summary=seed.get("content", "")[:300],
            ),
            agent_id="kagemi",
        )
    out = await tournament.ainvoke(
        {
            "mission_id": state["mission_id"],
            "playbook": state["playbook"],
            "mode": brief.mode,
            "topic": brief.topic,
            "question": brief.question,
            "context": brief.context,
            "code_context": brief.code_context,
            "feedback": feedback,
            "solvers": brief.solvers,
            "critic": brief.critic,
            "judge_id": "hakari",
            "proposals": dict(brief.seed_proposals),
            "scores": {},
            "labels": {},
            "round": 0,
            "max_rounds": min(brief.max_rounds, limit(state, "debate")),
            "threshold": 1.5,
            "reputation": _reputation_scores(await agent_stats(), brief.solvers, brief.topic),
            "verdict": None,
        },
        {"recursion_limit": 80},
    )
    verdict = Verdict.model_validate(out["verdict"])
    winner = out["proposals"][verdict.winner]
    for sid in brief.solvers:
        await reputation.bump(sid, tournaments=1, wins=1 if sid == verdict.winner else 0)
        status(sid, "success" if sid == verdict.winner else "idle")
    if verdict.winner in brief.solvers:
        await reputation.reward(verdict.winner, brief.topic, round(verdict.confidence, 2))

    round_no = count(state, "fix") + 1
    evidence = [
        EvidenceItem(
            kind="answer" if brief.mode == "answer" else "diff",
            title=f"Round {round_no} winner {verdict.winner_label} ({winner['strategy']})",
            content=winner["content"] if brief.mode == "answer" else _diff_text(winner),
        ).with_hash()
    ]
    if winner.get("tests"):
        t = winner["tests"]
        evidence.append(
            EvidenceItem(
                kind="test_report",
                title=f"Round {round_no} sandbox tests for {verdict.winner_label}",
                content=f"{t.get('passed', 0)} passed, {t.get('failed', 0)} failed, {t.get('errors', 0)} errors\n{t.get('output', '')[-3000:]}",
            ).with_hash()
        )
    return {
        "proposals": {"__reset__": True, **out["proposals"]},
        "scores": {"__reset__": True, **out["scores"]},
        "verdict": verdict.model_dump(mode="json"),
        "answer": winner["content"],
        "evidence": [e.model_dump() for e in evidence],
        "messages": [
            AIMessage(
                content=(
                    f"Verdict: {verdict.winner_label} wins (confidence {verdict.confidence:.2f}). "
                    f"{verdict.reasoning}"
                ),
                name="hakari",
            )
        ],
    }


def _diff_text(prop: dict[str, Any]) -> str:
    p = prop.get("patch") or {}
    minus = "\n".join(f"- {line}" for line in str(p.get("search", "")).splitlines())
    plus = "\n".join(f"+ {line}" for line in str(p.get("replace", "")).splitlines())
    return f"--- {p.get('file', '?')}\n{minus}\n{plus}"


async def validate(state: dict[str, Any]) -> dict[str, Any]:
    status("mamoru", "testing")
    result = await get_playbook(state["playbook"]).validate(state)
    status("mamoru", "success" if result.ok else "failed")
    update: dict[str, Any] = {"validation": result.model_dump()}
    if not result.ok:
        update["loops"] = {"fix": 1}
        update["failure_notes"] = note(state, f"validation failed: {result.summary}")
    if result.tests:
        update["evidence"] = [
            EvidenceItem(
                kind="test_report", title="Validation tests", content=str(result.tests)[:4000]
            )
            .with_hash()
            .model_dump()
        ]
    return update


def after_validate(state: dict[str, Any]) -> str:
    if (state.get("validation") or {}).get("ok"):
        return take("validate", "risk_gate", "pass")
    has_tournament = get_playbook(state["playbook"]).tournament_mode is not None
    if count(state, "fix") <= limit(state, "fix"):
        return take("validate", "council" if has_tournament else "synthesize", "fail → retry fix")
    if count(state, "replan") < limit(state, "replan"):
        return take("validate", "plan", "fail → replan")
    return take("validate", "report", "fail → give up")
