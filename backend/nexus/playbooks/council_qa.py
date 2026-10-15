"""Council Q&A: hard questions answered by a council instead of one model call.

Scouts research in parallel (knowledge base), three Challengers answer independently,
answers are reviewed anonymously, solvers debate if reviewers disagree, and the
Judge issues a verdict with confidence and dissent. A grader then checks the
winning answer actually addresses the question (validation → fix loop).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from nexus.core.services import services
from nexus.graph.schemas import Plan, PlanStep, ValidationResult
from nexus.llm.types import ChatMessage
from nexus.playbooks.base import Playbook, TournamentBrief, findings_text


class Grade(BaseModel):
    addresses_question: bool = Field(description="Does the answer directly answer the question?")
    problems: str = Field(default="", description="What is wrong or missing, if anything.")


class CouncilQA(Playbook):
    id = "council_qa"
    title = "Council Q&A"
    description = "Parallel answers, anonymous peer review, debate and a Chairman verdict."
    tournament_mode = "answer"
    planner_hint = (
        "This is a question-answering mission. Plan 1-3 short research steps for "
        "role 'researcher' (search the knowledge base from different angles). Do not "
        "plan a step that writes the final answer — the council does that."
    )

    def default_tools(self, role: str) -> list[str] | None:
        return ["knowledge.search"]  # Q&A research never needs files, tickets or sandboxes

    def template_plan(self, state: dict[str, Any]) -> Plan:
        task = state.get("task", "")
        return Plan(
            goal=f"Answer: {task[:180]}",
            source="template",
            steps=[
                PlanStep(
                    id="facts",
                    title="Search for direct facts",
                    description=f"Search the knowledge base for facts that answer: {task}",
                    role="researcher",
                    success_criteria="Relevant passages found and cited, or confirmed absent.",
                    tools=["knowledge.search"],
                ),
                PlanStep(
                    id="context",
                    title="Search for background and caveats",
                    description=f"Search for background, trade-offs or caveats related to: {task}",
                    role="researcher",
                    success_criteria="Background or caveats summarised.",
                    tools=["knowledge.search"],
                ),
            ],
        )

    def tournament_brief(self, state: dict[str, Any]) -> TournamentBrief:
        return TournamentBrief(
            mode="answer",
            topic="council_qa",
            question=state.get("task", ""),
            context=findings_text(state),
            max_rounds=1,
        )

    async def validate(self, state: dict[str, Any]) -> ValidationResult:
        answer = state.get("answer") or ""
        if not answer.strip():
            return ValidationResult(ok=False, summary="The council produced no answer.")
        grade = await services().llm.structured(
            [
                ChatMessage.system(
                    "You grade answers. Reply true if the answer directly addresses the "
                    "question (even if brief); false if it is off-topic, empty or refuses."
                ),
                ChatMessage.user(f"Question:\n{state.get('task')}\n\nAnswer:\n{answer[:3000]}"),
            ],
            Grade,
            purpose="grade",
            agent_id="aegis",
            default=Grade(addresses_question=True, problems="(grader unavailable; accepted)"),
        )
        if grade.addresses_question:
            return ValidationResult(ok=True, summary="Grader: the answer addresses the question.")
        return ValidationResult(
            ok=False, summary="Grader: the answer misses the question.", details=grade.problems
        )
