"""Simulation mode: a deterministic stand-in for the local models.

Enabled only with ``NEXUS_LLM_PROVIDER=simulation`` (used by the Playwright e2e
suite and offline demos). The UI shows a SIMULATION badge whenever it is on, so
scripted behaviour is never mistaken for live model output. Everything else —
graph, tools, sandbox, approvals, persistence, events — runs for real.
"""

from __future__ import annotations

import json
import re

from nexus.llm.scripted import ScriptedLLM
from nexus.llm.types import LLMRequest


def _react(req: LLMRequest) -> str:
    if any("Observation from" in m.content for m in req.messages):
        return json.dumps(
            {
                "thought": "The search results are enough.",
                "action": "final",
                "action_input": {},
                "final_answer": "Found the relevant passages in the knowledge base.",
            }
        )
    tools = re.findall(r"- ([a-z_]+\.[a-z_]+)\(", req.messages[0].content)
    if tools:
        tool = "knowledge.search" if "knowledge.search" in tools else tools[0]
        args = {"query": "reducers"} if tool == "knowledge.search" else {}
        return json.dumps({"thought": f"Let me use {tool}.", "action": tool, "action_input": args})
    return json.dumps(
        {
            "thought": "No tools needed.",
            "action": "final",
            "action_input": {},
            "final_answer": "Answered from context.",
        }
    )


def _review(req: LLMRequest) -> str:
    text = req.messages[-1].content
    m = re.search(r"Review exactly these labels: ([A-Z, ]+)\.", text)
    labels = [x.strip() for x in m.group(1).split(",")] if m else ["A"]
    blocks = dict(
        re.findall(r"### Proposal ([A-Z])\n(.*?)(?=\n### Proposal|\n\nReview exactly)", text, re.S)
    )
    out = []
    for lab in labels:
        good = "volt" in blocks.get(lab, "")
        s = 9 if good else 6
        out.append(
            {
                "label": lab,
                "correctness": s,
                "risk": 1 if good else 3,
                "simplicity": s,
                "completeness": s,
                "reason": "Precise and complete." if good else "Correct but thinner.",
            }
        )
    return json.dumps({"reviews": out})


def _solve(req: LLMRequest) -> str:
    who = req.agent_id or "solver"
    return json.dumps(
        {
            "answer": f"[{who}] ReAct interleaves reasoning and tool use step by step; Plan-and-Execute first writes a plan, then executes it, replanning on failure.",
            "rationale": "Standard definitions.",
        }
    )


def _plan(req: LLMRequest) -> str:
    return json.dumps(
        {
            "goal": "Answer the question",
            "steps": [
                {
                    "id": "facts",
                    "title": "Search for facts",
                    "description": "Search the knowledge base",
                    "role": "researcher",
                },
                {
                    "id": "context",
                    "title": "Search for context",
                    "description": "Search for background",
                    "role": "researcher",
                },
            ],
        }
    )


def _page_spec(req: LLMRequest) -> str:
    return json.dumps(
        {
            "kind": "blog",
            "title": "How AI Agents Work Together",
            "tagline": "A short tour of planning, tools and human approval.",
            "audience": "curious developers",
            "accent": "indigo",
            "sections": [
                {"heading": "What an Agent Is", "points": "Definition and examples."},
                {"heading": "Teams of Agents", "points": "Why several agents beat one."},
                {"heading": "Keeping Humans in Control", "points": "Approvals and safety."},
            ],
        }
    )


def _section(req: LLMRequest) -> str:
    heading = re.search(r"Section heading: (.+)", req.messages[-1].content)
    topic = heading.group(1) if heading else "this topic"
    sentence = (
        f"{topic} is explained here in plain words for a developer who is new to agents. "
        "Each agent has a role, a small set of tools and a clear goal, and it reports what it "
        "did so the next agent can build on it. "
    )
    return json.dumps(
        {
            "paragraphs": [sentence * 2, sentence + "The result is checked before anyone sees it."],
            "bullets": ["Clear roles", "Small, safe tools", "Every step is recorded"],
        }
    )


def _ticket(req: LLMRequest) -> str:
    return json.dumps(
        {
            "title": "Order pipeline rejects valid orders",
            "summary": "The order pipeline raises an error for some valid orders, so they are "
            "never processed and customers do not get a confirmation (simulation).",
            "steps": ["Place a guest order", "Watch the pipeline logs"],
            "expected": "The order is processed.",
            "actual": "The pipeline raises an error and drops the order.",
            "suspected_file": "app/pipeline.py",
            "severity": "high",
            "labels": ["bug", "pipeline"],
        }
    )


def simulation_llm() -> ScriptedLLM:
    return ScriptedLLM(
        {
            "rewrite": json.dumps(
                {
                    "goal": "Answer the request",
                    "clarified_task": "Answer the user's request clearly.",
                }
            ),
            "route": json.dumps({"playbook": "council_qa", "reason": "a question (simulation)"}),
            "plan": _plan,
            "plan:page": _page_spec,
            "write": _section,
            "ticket": _ticket,
            "replan": _plan,
            "react": _react,
            "solve": _solve,
            "review": _review,
            "debate": json.dumps({"decision": "defend", "rationale": "kept"}),
            "judge": json.dumps(
                {"reasoning": "Proposal by Volt was the most precise (simulation)."}
            ),
            "grade": json.dumps({"addresses_question": True, "problems": ""}),
            "summarise": "The team found that ReAct interleaves reasoning with actions while Plan-and-Execute plans first (simulation).",
            "guide": "This is simulation mode, so I answer from a script: I can still navigate the app for you.",
        },
        default="OK (simulation)",
    )
