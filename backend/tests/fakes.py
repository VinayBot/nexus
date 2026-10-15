"""Deterministic scripts for whole missions (offline, CI-friendly)."""

from __future__ import annotations

import json
import re
from typing import Any

from nexus.agents.toolbox import LocalToolBox
from nexus.llm.demo_tools import TOOL_FNS, TOOL_SPECS
from nexus.llm.scripted import ScriptedLLM
from nexus.llm.types import LLMRequest, ToolSpec

KNOWLEDGE = {
    "langgraph": "LangGraph models agents as state machines with checkpoints and reducers.",
    "reducer": "A reducer merges concurrent updates to one state key.",
}


def knowledge_search(query: str, collection: str = "docs", k: int = 3) -> str:
    hits = [v for key, v in KNOWLEDGE.items() if key in query.lower()]
    return "\n".join(hits) or "No matching documents."


def local_toolbox() -> LocalToolBox:
    tools: dict[str, tuple[ToolSpec, Any]] = {
        "knowledge.search": (
            ToolSpec(
                name="knowledge.search",
                description="Search the knowledge base.",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            ),
            knowledge_search,
        )
    }
    for spec in TOOL_SPECS:
        tools[f"demo.{spec.name}"] = (
            spec.model_copy(update={"name": f"demo.{spec.name}"}),
            TOOL_FNS[spec.name],
        )
    return LocalToolBox(tools)


def react_script(req: LLMRequest) -> str:
    """Search once, then answer from the observation."""
    observed = any("Observation from" in m.content for m in req.messages)
    if observed:
        return json.dumps(
            {
                "thought": "I have what I need.",
                "action": "final",
                "action_input": {},
                "final_answer": "Reducers merge parallel updates (source: knowledge.search).",
            }
        )
    return json.dumps(
        {
            "thought": "Search the docs first.",
            "action": "knowledge.search",
            "action_input": {"query": "reducer langgraph"},
        }
    )


def review_script(req: LLMRequest) -> str:
    """Reviewers clearly prefer whichever masked proposal Ronin B wrote."""
    text = req.messages[-1].content
    m = re.search(r"Review exactly these labels: ([A-Z, ]+)\.", text)
    labels = [x.strip() for x in m.group(1).split(",")] if m else ["A"]
    blocks = dict(
        re.findall(r"### Proposal ([A-Z])\n(.*?)(?=\n### Proposal|\n\nReview exactly)", text, re.S)
    )
    reviews = []
    for lab in labels:
        good = "ronin_b" in blocks.get(lab, "")
        s = 9 if good else 5
        reviews.append(
            {
                "label": lab,
                "correctness": s,
                "risk": 1 if good else 4,
                "simplicity": s,
                "completeness": s,
                "reason": "Clear and correct." if good else "Vague.",
            }
        )
    return json.dumps({"reviews": reviews})


def solve_script(req: LLMRequest) -> str:
    who = req.agent_id or "?"
    return json.dumps(
        {
            "answer": f"{who}: a reducer merges concurrent updates to a key.",
            "rationale": "From the docs.",
        }
    )


def council_llm(**overrides: Any) -> ScriptedLLM:
    llm = ScriptedLLM(
        {
            "rewrite": json.dumps(
                {
                    "goal": "Explain reducers",
                    "clarified_task": "Explain what a LangGraph reducer is.",
                    "constraints": [],
                    "keywords": ["reducer"],
                    "is_vague": False,
                }
            ),
            "route": json.dumps({"playbook": "council_qa", "reason": "a question"}),
            "plan": json.dumps(
                {
                    "goal": "Explain reducers",
                    "steps": [
                        {
                            "id": "facts",
                            "title": "Find facts",
                            "description": "search docs",
                            "role": "researcher",
                        },
                        {
                            "id": "context",
                            "title": "Find context",
                            "description": "search more",
                            "role": "researcher",
                        },
                    ],
                }
            ),
            "react": react_script,
            "solve": solve_script,
            "review": review_script,
            "debate": json.dumps({"decision": "defend", "rationale": "fine"}),
            "judge": json.dumps({"reasoning": "B had the best evidence."}),
            "grade": json.dumps({"addresses_question": True, "problems": ""}),
            "summarise": "- summary",
        }
    )
    for k, v in overrides.items():
        llm.on(k, v)
    return llm
