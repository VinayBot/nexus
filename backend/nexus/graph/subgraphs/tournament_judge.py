"""The tournament's last node: pick the winner from the evidence, then let the judge agent
explain the decision in plain words."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from nexus.core.event_types import CouncilVerdict
from nexus.core.events import agent_context, emit
from nexus.core.services import services
from nexus.graph.subgraphs.scoring import judge
from nexus.graph.subgraphs.tournament_prompts import render
from nexus.llm.types import ChatMessage


class JudgeNote(BaseModel):
    reasoning: str = Field(description="2-3 sentences explaining the decision.")


async def judge_node(state: Mapping[str, Any]) -> dict[str, Any]:
    """Evidence-weighted verdict (scoring.judge), explained in a sentence by the judge agent."""
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
                    f"{render(winner, state['mode'])}\n\nScore breakdown: {breakdown}\n"
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
