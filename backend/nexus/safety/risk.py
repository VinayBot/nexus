"""Risk Scorer: rule-based factors → score in [0, 1] → level → gate route.

    LOW (<0.25)       auto-execute (logged)
    MEDIUM (<0.50)    single human approval
    HIGH (<0.75)      approval + mandatory sandbox dry-run
    CRITICAL (≥0.75)  blocked unless a human explicitly overrides

Policies can only make a route *stricter* (e.g. "no email without approval").
Historical owner decisions for the same action kind nudge the score: frequent
rejections raise it; a clean approval streak lowers it slightly.
"""

from __future__ import annotations

from typing import Any

from nexus.graph.schemas import ProposedAction, RiskAssessment, RiskLevel
from nexus.safety.policies import PolicyEngine, Route, stricter

ACTION_BASE: dict[str, float] = {
    "deliver_answer": 0.0,
    "run_team": 0.15,
    "comment_ticket": 0.2,
    "write_project": 0.25,
    "publish_page": 0.25,
    "send_email": 0.3,
    "apply_patch": 0.35,
}
BLAST: dict[str, float] = {"none": 0.0, "local": 0.05, "service": 0.15, "external": 0.25}


def level_for(score: float) -> RiskLevel:
    if score < 0.25:
        return "LOW"
    if score < 0.5:
        return "MEDIUM"
    if score < 0.75:
        return "HIGH"
    return "CRITICAL"


ROUTE_FOR: dict[RiskLevel, Route] = {
    "LOW": "auto",
    "MEDIUM": "approve",
    "HIGH": "dry_run",
    "CRITICAL": "blocked",
}


def score_risk(
    action: ProposedAction,
    *,
    tests: dict[str, Any] | None = None,
    verdict: dict[str, Any] | None = None,
    history: dict[str, int] | None = None,
    policies: PolicyEngine | None = None,
) -> RiskAssessment:
    f: dict[str, float] = {
        "action_type": ACTION_BASE.get(action.kind, 0.3),
        "blast_radius": BLAST[action.blast_radius],
        "files_touched": min(0.15, 0.05 * len(action.files_touched)),
        "diff_size": round(min(0.15, action.diff_lines / 200), 3),
    }
    if action.kind in {"apply_patch", "write_project"}:
        if tests is None:
            f["tests"] = 0.1
        elif tests.get("ok"):
            f["tests"] = -0.1
        else:
            f["tests"] = 0.3
    if verdict:
        f["tournament_confidence"] = round((1 - float(verdict.get("confidence", 1))) * 0.2, 3)
        if verdict.get("escalate"):
            f["tournament_escalation"] = 0.15
    if history:
        approved, rejected = history.get("approved", 0), history.get("rejected", 0)
        if approved + rejected:
            f["owner_history"] = round(0.2 * rejected / (approved + rejected), 3)
            if approved >= 3 and rejected == 0:
                f["owner_history"] = -0.05

    score = round(min(1.0, max(0.0, sum(f.values()))), 3)
    level = level_for(score)
    route: Route = ROUTE_FOR[level]
    notes = [f"score {score:.2f} → {level}"]
    if policies is not None:
        required, hits = policies.min_route(action.kind)
        if hits and stricter(route, required) != route:
            route = stricter(route, required)
            notes.append(f"policy {', '.join(hits)} requires approval")
        if level == "CRITICAL" and not policies.blocks_level("CRITICAL"):
            route = "dry_run"
            notes.append("CRITICAL block policy disabled → approval + dry-run")
    top = sorted(((v, k) for k, v in f.items() if v > 0), reverse=True)[:3]
    if top:
        notes.append("main factors: " + ", ".join(f"{k} (+{v:.2f})" for v, k in top))
    return RiskAssessment(
        level=level, score=score, factors=f, route=route, explanation="; ".join(notes)
    )
