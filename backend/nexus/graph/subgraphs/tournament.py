"""Council / Solution Tournament subgraph.

    START ─Send×N→ propose ─→ ground ─→ mask ─Send×M→ review ─→ converge
                                  ↑                                  │
                                  └──────── revise ←─Send×N── (diverged & rounds left)
                                                                     │
                                                                   judge → END

* **propose** — N solvers answer independently, in parallel (same model,
  different persona/strategy/temperature).
* **ground** — code mode: each patch runs in its own sandbox (repro + existing
  tests); results are attached to the proposal.
* **mask** — proposals are relabelled A/B/C in a shuffled order.
* **review** — every solver plus the Critic scores the *other* proposals.
* **converge** — if reviewer scores diverge beyond the threshold and debate
  rounds remain, solvers see critiques and may defend or revise (a cycle).
* **judge** — evidence-weighted final score, winner, runner-up, confidence,
  dissent; low confidence or failing tests escalate to human approval.
"""

from __future__ import annotations

import asyncio
import random
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from nexus.core.event_types import (
    CouncilMasked,
    CouncilProposal,
    CouncilReview,
    CouncilRound,
    SandboxTestResult,
)
from nexus.core.events import agent_context, emit
from nexus.core.services import services
from nexus.graph.instrument import instrument
from nexus.graph.reducers import merge_dict, merge_scores
from nexus.graph.schemas import Proposal, Review
from nexus.graph.subgraphs.scoring import divergence
from nexus.graph.subgraphs.tournament_judge import judge_node
from nexus.graph.subgraphs.tournament_prompts import render, solver_prompt
from nexus.graph.subgraphs.tournament_schemas import (
    AnswerOut,
    CodeOut,
    ReviewBatch,
    ReviewItem,
    Revision,
    line_patch,
)
from nexus.llm.types import ChatMessage

LABELS = "ABCDEFG"


class TournamentState(TypedDict, total=False):
    mission_id: str
    playbook: str
    mode: Literal["answer", "code"]
    topic: str
    question: str
    context: str
    code_context: dict[str, Any] | None  # code mode: {"files": {path: content}}
    feedback: str  # why the previous winner failed validation (fix loop)
    solvers: list[str]
    critic: str | None
    judge_id: str
    proposals: Annotated[dict[str, Any], merge_dict]
    scores: Annotated[dict[str, Any], merge_scores]
    labels: dict[str, str]  # label -> solver id
    round: int
    max_rounds: int
    threshold: float
    divergence: float
    debate: bool
    reputation: dict[str, float]
    verdict: dict[str, Any] | None
    breakdown: dict[str, Any]


# --- nodes --------------------------------------------------------------------------
def fan_out_proposals(state: TournamentState) -> list[Send]:
    return [Send("propose", {**state, "solver": sid}) for sid in state["solvers"]]


async def propose(payload: dict[str, Any]) -> dict[str, Any]:
    sid = payload["solver"]
    spec = services().registry.get(sid)
    token = agent_context.set(sid)
    try:
        msgs = solver_prompt(sid, payload)
        if payload["mode"] == "code":
            code = await services().llm.structured(
                msgs,
                CodeOut,
                purpose="solve",
                role="code",
                agent_id=sid,
                temperature=spec.temperature,
            )
            files = (payload.get("code_context") or {}).get("files", {})
            prop = Proposal(
                solver_id=sid,
                strategy=spec.strategy or spec.title,
                content=code.rationale,
                rationale=code.rationale,
                patch=line_patch(
                    files, code.file, code.start_line, code.end_line, code.replacement
                ),
            )
        else:
            ans = await services().llm.structured(
                msgs, AnswerOut, purpose="solve", agent_id=sid, temperature=spec.temperature
            )
            prop = Proposal(
                solver_id=sid,
                strategy=spec.strategy or spec.title,
                content=ans.answer,
                rationale=ans.rationale,
            )
    finally:
        agent_context.reset(token)
    emit(
        "council.proposal",
        CouncilProposal(solver_id=sid, strategy=prop.strategy, summary=prop.content[:300]),
        agent_id=sid,
    )
    return {"proposals": {sid: prop.model_dump(mode="json")}}


async def ground(state: TournamentState) -> dict[str, Any]:
    """Code mode: run every untested patch in its own sandbox."""
    if state.get("mode") != "code":
        return {}
    from nexus.playbooks import get_playbook

    playbook = get_playbook(state["playbook"])
    pending = {
        sid: p
        for sid, p in state.get("proposals", {}).items()
        if p.get("patch") and not p.get("tests")
    }

    async def one(sid: str, prop: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        tests = await playbook.ground(prop, dict(state))
        emit(
            "sandbox.test_result",
            SandboxTestResult(
                target=sid,
                passed=tests.get("passed", 0),
                failed=tests.get("failed", 0),
                errors=tests.get("errors", 0),
                ok=bool(tests.get("ok")),
                duration_ms=tests.get("duration_ms", 0.0),
                backend=tests.get("backend", "?"),
                summary=str(tests.get("summary", ""))[:300],
            ),
            agent_id=sid,
        )
        return sid, {**prop, "tests": tests}

    results = await asyncio.gather(*(one(s, p) for s, p in pending.items()))
    return {"proposals": dict(results)}


async def mask(state: TournamentState) -> dict[str, Any]:
    if state.get("labels"):
        return {}
    solvers = list(state.get("proposals", {}))
    rng = random.Random(f"{state.get('mission_id', '')}:{state.get('topic', '')}")
    rng.shuffle(solvers)
    labels = {LABELS[i]: sid for i, sid in enumerate(solvers)}
    emit("council.masked", CouncilMasked(labels=list(labels)))
    return {"labels": labels}


def fan_out_reviews(state: TournamentState) -> list[Send]:
    reviewers = [*state["solvers"], *([state["critic"]] if state.get("critic") else [])]
    return [Send("review", {**state, "reviewer": r}) for r in reviewers]


async def review(payload: dict[str, Any]) -> dict[str, Any]:
    reviewer = payload["reviewer"]
    spec = services().registry.get(reviewer)
    labels: dict[str, str] = payload["labels"]
    targets = {lab: sid for lab, sid in labels.items() if sid != reviewer}
    if not targets:
        return {}
    shown = "\n\n".join(
        f"### Proposal {lab}\n{render(payload['proposals'][sid], payload['mode'])}"
        for lab, sid in targets.items()
    )
    msgs = [
        ChatMessage.system(
            f"{spec.system_prompt.strip()}\n\nYou are reviewing anonymous proposals. Score "
            "each 0-10 on correctness, risk (10 = very risky), simplicity and completeness, "
            "and give a one-sentence reason. Be fair and specific."
        ),
        ChatMessage.user(
            f"Problem:\n{payload['question']}\n\n{shown}\n\n"
            f"Review exactly these labels: {', '.join(targets)}."
        ),
    ]
    token = agent_context.set(reviewer)
    try:
        batch = await services().llm.structured(
            msgs,
            ReviewBatch,
            purpose="review",
            agent_id=reviewer,
            default=ReviewBatch(
                reviews=[
                    ReviewItem(
                        label=lab,
                        correctness=5,
                        risk=5,
                        simplicity=5,
                        completeness=5,
                        reason="(no review: model output invalid)",
                    )
                    for lab in targets
                ]
            ),
        )
    finally:
        agent_context.reset(token)
    update: dict[str, Any] = {}
    for item in batch.reviews:
        lab = item.label.strip().upper()[:1]
        if lab not in targets:
            continue
        r = Review(
            reviewer=reviewer,
            correctness=item.correctness,
            risk=item.risk,
            simplicity=item.simplicity,
            completeness=item.completeness,
            reason=item.reason[:400],
        )
        emit(
            "council.review",
            CouncilReview(
                reviewer=reviewer,
                target_label=lab,
                score=r.score,
                scores={
                    "correctness": r.correctness,
                    "risk": r.risk,
                    "simplicity": r.simplicity,
                    "completeness": r.completeness,
                },
                reason=r.reason,
            ),
            agent_id=reviewer,
        )
        update[targets[lab]] = {"reviews": [r.model_dump()]}
    return {"scores": update}


async def converge(state: TournamentState) -> dict[str, Any]:
    div = divergence(state.get("scores", {}))
    rnd = state.get("round", 0)
    debate = div > state.get("threshold", 1.5) and rnd < state.get("max_rounds", 1)
    emit("council.round", CouncilRound(round=rnd + 1, divergence=div, converged=not debate))
    return {"divergence": div, "debate": debate, "round": rnd + 1 if debate else rnd}


def after_converge(state: TournamentState) -> list[Send] | str:
    if not state.get("debate"):
        return "judge"
    return [Send("revise", {**state, "solver": sid}) for sid in state["solvers"]]


async def revise(payload: dict[str, Any]) -> dict[str, Any]:
    sid = payload["solver"]
    mine = payload["proposals"].get(sid)
    if not mine:
        return {}
    critiques = [r["reason"] for r in payload.get("scores", {}).get(sid, {}).get("reviews", [])]
    msgs = [
        *solver_prompt(sid, payload),
        ChatMessage.assistant(render(mine, payload["mode"])),
        ChatMessage.user(
            "Reviewers critiqued your proposal:\n- "
            + "\n- ".join(critiques or ["(none)"])
            + "\n\nEither defend it (decision 'defend') or revise it (decision 'revise' with the "
            "full new answer, or in code mode a new file/start_line/end_line/replacement)."
        ),
    ]
    token = agent_context.set(sid)
    try:
        rev = await services().llm.structured(
            msgs,
            Revision,
            purpose="debate",
            agent_id=sid,
            default=Revision(decision="defend", rationale="(kept original)"),
        )
    finally:
        agent_context.reset(token)
    if rev.decision == "defend":
        return {}
    new = dict(mine)
    new["round"] = payload.get("round", 1)
    new["rationale"] = rev.rationale
    if payload["mode"] == "code" and rev.start_line and rev.replacement is not None:
        files = (payload.get("code_context") or {}).get("files", {})
        new["patch"] = line_patch(
            files,
            rev.file or mine["patch"]["file"],
            rev.start_line,
            rev.end_line or rev.start_line,
            rev.replacement,
        )
        new["tests"] = None  # must be re-grounded
    elif rev.answer:
        new["content"] = rev.answer
    emit(
        "council.proposal",
        CouncilProposal(
            solver_id=sid, strategy=mine["strategy"], summary=f"(revised) {new['content'][:280]}"
        ),
        agent_id=sid,
    )
    return {"proposals": {sid: new}}


def build_tournament() -> CompiledStateGraph[Any, Any, Any, Any]:
    g = StateGraph(TournamentState)
    g.add_node("propose", instrument("council.propose", propose))
    g.add_node("ground", instrument("council.ground", ground))
    g.add_node("mask", instrument("council.mask", mask))
    g.add_node("review", instrument("council.review", review))
    g.add_node("converge", instrument("council.converge", converge))
    g.add_node("revise", instrument("council.revise", revise))
    g.add_node("judge", instrument("council.judge", judge_node))
    g.add_conditional_edges(START, fan_out_proposals, ["propose"])
    g.add_edge("propose", "ground")
    g.add_edge("ground", "mask")
    g.add_conditional_edges("mask", fan_out_reviews, ["review"])
    g.add_edge("review", "converge")
    g.add_conditional_edges("converge", after_converge, ["revise", "judge"])
    g.add_edge("revise", "ground")
    g.add_edge("judge", END)
    return g.compile(checkpointer=False, name="tournament")


tournament = build_tournament()
