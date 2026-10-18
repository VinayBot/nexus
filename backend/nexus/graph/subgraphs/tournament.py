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
import re
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

from nexus.core.event_types import (
    CouncilMasked,
    CouncilProposal,
    CouncilReview,
    CouncilRound,
    CouncilVerdict,
    SandboxTestResult,
)
from nexus.core.events import agent_context, emit
from nexus.core.services import services
from nexus.graph.instrument import instrument
from nexus.graph.reducers import merge_dict, merge_scores
from nexus.graph.schemas import Proposal, Review
from nexus.graph.subgraphs.scoring import divergence, judge
from nexus.llm.types import ChatMessage
from nexus.safety.guardrails import UNTRUSTED_RULE

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


# --- LLM output schemas -------------------------------------------------------------
class AnswerOut(BaseModel):
    answer: str = Field(description="Your complete answer.")
    rationale: str = Field(default="", description="Why this answer is right, briefly.")


class CodeOut(BaseModel):
    """Line-range edit: small models rewrite lines far more reliably than they copy them."""

    rationale: str = Field(description="Root cause and why this edit fixes it.")
    file: str = Field(description="Which of the shown files to edit.")
    start_line: int = Field(ge=1, description="First line number to replace.")
    end_line: int = Field(
        ge=1, description="Last line number to replace (same as start for one line)."
    )
    replacement: str = Field(
        description="The new full lines that replace that range, with indentation."
    )


class ReviewItem(BaseModel):
    label: str
    correctness: float = Field(ge=0, le=10)
    risk: float = Field(ge=0, le=10, description="10 = very risky")
    simplicity: float = Field(ge=0, le=10)
    completeness: float = Field(ge=0, le=10)
    reason: str = Field(description="One or two sentences.")


class ReviewBatch(BaseModel):
    reviews: list[ReviewItem]


class Revision(BaseModel):
    decision: Literal["defend", "revise"]
    rationale: str
    answer: str | None = None
    file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    replacement: str | None = None


_NUMBERED = re.compile(r"^\s*\d+\s*\|\s?")


def line_patch(
    files: dict[str, str], file: str, start: int, end: int, replacement: str
) -> dict[str, Any]:
    """Turn a line-range edit into the exact search/replace patch the grounder applies."""
    if file not in files:
        file = next(iter(files), file)
    lines = files.get(file, "").splitlines()
    start, end = min(start, end), max(start, end)
    if not lines or start > len(lines):
        return {"file": file, "search": "", "replace": replacement, "lines": [start, end]}
    end = min(end, len(lines))
    # models sometimes echo the " 12| " prefixes we show them
    cleaned = "\n".join(_NUMBERED.sub("", ln) for ln in replacement.strip("\n").splitlines())
    return {
        "file": file,
        "search": "\n".join(lines[start - 1 : end]),
        "replace": cleaned,
        "lines": [start, end],
    }


def numbered(content: str) -> str:
    return "\n".join(f"{i:3d}| {line}" for i, line in enumerate(content.splitlines(), 1))


# --- helpers ------------------------------------------------------------------------
def _solver_prompt(sid: str, state: dict[str, Any]) -> list[ChatMessage]:
    spec = services().registry.get(sid)
    sys = f"{spec.system_prompt.strip()}\n\n{UNTRUSTED_RULE}"
    parts = [f"Problem:\n{state['question']}"]
    if state.get("context"):
        parts.append(f"What the team found:\n{state['context']}")
    if state.get("mode") == "answer":
        parts.append(
            "Answer the problem directly. If the team's findings are thin or irrelevant, "
            "answer from your own knowledge and say which parts are not from the findings."
        )
    if state.get("mode") == "code" and state.get("code_context"):
        cc = state["code_context"]
        for path, content in cc["files"].items():
            parts.append(f"File {path} (line numbers on the left):\n```\n{numbered(content)}\n```")
        focus = cc.get("focus")
        if focus:
            parts.append(
                f"The exception is raised in {focus['file']} at line {focus['line']}:\n    {focus['code']}"
            )
        parts.append(
            "Fix it with ONE edit: give the file, start_line and end_line of the lines to replace, "
            "and 'replacement' = the corrected full lines (keep the indentation, no line numbers). "
            "Change as little as your strategy requires."
        )
    if state.get("feedback"):
        parts.append(f"A previous attempt failed validation:\n{state['feedback']}")
    return [ChatMessage.system(sys), ChatMessage.user("\n\n".join(parts))]


def _render(prop: dict[str, Any], mode: str) -> str:
    if mode == "code" and prop.get("patch"):
        p = prop["patch"]
        tests = prop.get("tests") or {}
        t = (
            f"\nSandbox tests: {tests.get('passed', 0)} passed, {tests.get('failed', 0)} failed"
            if tests
            else ""
        )
        return f"Rationale: {prop.get('rationale', '')}\n--- search\n{p['search']}\n+++ replace\n{p['replace']}{t}"
    return f"{prop['content']}\n(Rationale: {prop.get('rationale', '')})"


# --- nodes --------------------------------------------------------------------------
def fan_out_proposals(state: TournamentState) -> list[Send]:
    return [Send("propose", {**state, "solver": sid}) for sid in state["solvers"]]


async def propose(payload: dict[str, Any]) -> dict[str, Any]:
    sid = payload["solver"]
    spec = services().registry.get(sid)
    token = agent_context.set(sid)
    try:
        msgs = _solver_prompt(sid, payload)
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
        f"### Proposal {lab}\n{_render(payload['proposals'][sid], payload['mode'])}"
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
        *_solver_prompt(sid, payload),
        ChatMessage.assistant(_render(mine, payload["mode"])),
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


class JudgeNote(BaseModel):
    reasoning: str = Field(description="2-3 sentences explaining the decision.")


async def judge_node(state: TournamentState) -> dict[str, Any]:
    verdict, breakdown = judge(
        mode=state["mode"],
        proposals=state.get("proposals", {}),
        scores=state.get("scores", {}),
        labels=state.get("labels", {}),
        critic_id=state.get("critic"),
        reputation=state.get("reputation", {}),
        rounds=state.get("round", 0) + 1,
        divergence_threshold=state.get("threshold", 1.5),
    )
    judge_id = state.get("judge_id", "arbiter")
    winner = state["proposals"][verdict.winner]
    token = agent_context.set(judge_id)
    try:
        note = await services().llm.structured(
            [
                ChatMessage.system(services().registry.get(judge_id).system_prompt),
                ChatMessage.user(
                    f"Problem: {state['question']}\n\nWinning proposal ({verdict.winner_label}):\n"
                    f"{_render(winner, state['mode'])}\n\nScore breakdown: {breakdown}\n"
                    f"Main dissent: {verdict.dissent}\n\nExplain the decision briefly."
                ),
            ],
            JudgeNote,
            purpose="judge",
            agent_id=judge_id,
            default=JudgeNote(reasoning="Highest evidence-weighted score."),
        )
    finally:
        agent_context.reset(token)
    verdict = verdict.model_copy(update={"reasoning": note.reasoning})
    emit(
        "council.verdict",
        CouncilVerdict(
            winner=verdict.winner,
            winner_label=verdict.winner_label,
            runner_up=verdict.runner_up,
            confidence=verdict.confidence,
            dissent=verdict.dissent,
            final_scores=verdict.final_scores,
            escalate=verdict.escalate,
        ),
        agent_id=judge_id,
    )
    return {"verdict": verdict.model_dump(mode="json"), "breakdown": breakdown}


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
