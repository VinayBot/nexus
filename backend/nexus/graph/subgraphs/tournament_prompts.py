"""The prompts tournament solvers see, and how a proposal is shown to its reviewers."""

from __future__ import annotations

from typing import Any

from nexus.core.services import services
from nexus.graph.subgraphs.tournament_schemas import numbered
from nexus.llm.types import ChatMessage
from nexus.safety.guardrails import UNTRUSTED_RULE


def solver_prompt(sid: str, state: dict[str, Any]) -> list[ChatMessage]:
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
        for d in cc.get("named") or []:
            parts.append(
                f"The error message names {d['name']}, defined in {d['file']} at line "
                f"{d['line']}:\n    {d['code']}\nThe raising line may only be the symptom: check "
                "whether this definition is the real cause."
            )
        parts.append(
            "Fix it with ONE edit: give the file, start_line and end_line of the lines to replace, "
            "and 'replacement' = the corrected full lines (keep the indentation, no line numbers). "
            "Change as little as your strategy requires."
        )
    if state.get("feedback"):
        parts.append(f"A previous attempt failed validation:\n{state['feedback']}")
    return [ChatMessage.system(sys), ChatMessage.user("\n\n".join(parts))]


def render(prop: dict[str, Any], mode: str) -> str:
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
