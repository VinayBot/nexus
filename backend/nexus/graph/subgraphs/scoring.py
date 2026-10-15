"""Pure scoring maths for the Council/Tournament (unit-tested, no I/O).

Why evidence first: the solvers share one underlying model, so they share its
blind spots — three copies of the same wrong idea can review each other
favourably. Sandbox test results are independent of the model, so in code mode
they carry the largest weight and a failing winner always escalates to a human.
"""

from __future__ import annotations

import statistics
from typing import Any, Literal

from nexus.graph.schemas import Review, ScoreCard, Verdict

Mode = Literal["answer", "code"]

WEIGHTS: dict[Mode, dict[str, float]] = {
    "code": {"tests": 0.45, "peer": 0.25, "critic": 0.10, "size": 0.10, "reputation": 0.10},
    "answer": {"tests": 0.0, "peer": 0.70, "critic": 0.20, "size": 0.0, "reputation": 0.10},
}


def cards(scores: dict[str, Any]) -> dict[str, ScoreCard]:
    return {
        pid: ScoreCard.model_validate({**card, "proposal_id": pid}) for pid, card in scores.items()
    }


def divergence(scores: dict[str, Any]) -> float:
    """Mean per-proposal standard deviation of reviewer scores (0 = full agreement)."""
    spreads = []
    for card in cards(scores).values():
        values = [r.score for r in card.reviews]
        if len(values) >= 2:
            spreads.append(statistics.pstdev(values))
    return round(statistics.fmean(spreads), 2) if spreads else 0.0


def test_score(tests: dict[str, Any] | None) -> float:
    if not tests:
        return 0.0
    total = int(tests.get("passed", 0)) + int(tests.get("failed", 0)) + int(tests.get("errors", 0))
    if total == 0:
        return 0.0
    return round(10 * int(tests.get("passed", 0)) / total, 2)


def size_score(patch: dict[str, Any] | None) -> float:
    if not patch:
        return 5.0
    changed = abs(
        len(str(patch.get("replace", "")).splitlines())
        - len(str(patch.get("search", "")).splitlines())
    )
    changed += max(len(str(patch.get("replace", "")).splitlines()), 1)
    return round(max(0.0, 10 - changed / 3), 2)


def critic_score(card: ScoreCard, critic_id: str | None) -> float:
    for r in card.reviews:
        if r.reviewer == critic_id:
            return round(10 - r.risk, 2)
    return 5.0


def judge(
    *,
    mode: Mode,
    proposals: dict[str, Any],
    scores: dict[str, Any],
    labels: dict[str, str],
    critic_id: str | None,
    reputation: dict[str, float],
    rounds: int,
    divergence_threshold: float = 1.5,
) -> tuple[Verdict, dict[str, dict[str, float]]]:
    """Weighted final scores → winner, runner-up, confidence, dissent, escalation."""
    w = WEIGHTS[mode]
    by_card = cards(scores)
    breakdown: dict[str, dict[str, float]] = {}
    for sid, prop in proposals.items():
        card = by_card.get(sid, ScoreCard(proposal_id=sid))
        parts = {
            "tests": test_score(prop.get("tests")),
            "peer": card.mean,
            "critic": critic_score(card, critic_id),
            "size": size_score(prop.get("patch")),
            "reputation": min(10.0, reputation.get(sid, 5.0)),
        }
        parts["final"] = round(sum(parts[k] * w[k] for k in w), 3)
        breakdown[sid] = parts

    ranked = sorted(breakdown, key=lambda s: breakdown[s]["final"], reverse=True)
    winner = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    margin = breakdown[winner]["final"] - (breakdown[runner_up]["final"] if runner_up else 0)
    div = divergence(scores)
    confidence = 0.5 + (margin / 10) * 2.5 - div / 20
    winner_tests = proposals[winner].get("tests")
    tests_failed = mode == "code" and (not winner_tests or not winner_tests.get("ok"))
    if tests_failed:
        confidence *= 0.5
    confidence = round(min(0.99, max(0.05, confidence)), 2)
    escalate = confidence < 0.6 or div > divergence_threshold * 1.5 or tests_failed

    label_of = {sid: label for label, sid in labels.items()}
    harshest: Review | None = None
    winner_card = by_card.get(winner)
    if winner_card and winner_card.reviews:
        harshest = min(winner_card.reviews, key=lambda r: r.score)
    dissent = (
        f"{harshest.reviewer} scored {label_of.get(winner, winner)} lowest "
        f"({harshest.score:.1f}/10): {harshest.reason}"
        if harshest
        else "No reviews were recorded."
    )
    verdict = Verdict(
        winner=winner,
        winner_label=label_of.get(winner, winner),
        runner_up=runner_up,
        confidence=confidence,
        dissent=dissent[:600],
        final_scores={sid: b["final"] for sid, b in breakdown.items()},
        rounds=rounds,
        escalate=escalate,
    )
    return verdict, breakdown
