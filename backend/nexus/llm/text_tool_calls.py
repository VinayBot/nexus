"""Tool calls that a small model wrote as text instead of a structured ``tool_calls``.

Native function calling is the default, but 3B models sometimes print the call:
as a ReAct JSON turn (``{"action": ..., "action_input": ...}``), as a bare JSON call
(``{"name": ..., "arguments": ...}``), or in prose as ``tool(arg="x")``. These helpers
recover the call so the step is not lost.
"""

from __future__ import annotations

import ast
import re
from typing import Any

from nexus.llm.types import ChatMessage, ToolCall
from nexus.reliability.json_repair import JsonRepairError, extract_json

FINAL = "final"


def calls_in_text(
    content: str, tool_names: set[str] | None = None
) -> tuple[str, list[ToolCall], str | None]:
    """A tool call or ReAct turn written as JSON text: (thought, calls, final) or no calls."""
    try:
        data = extract_json(content)
    except JsonRepairError:
        return "", [], None
    if not isinstance(data, dict):
        return "", [], None
    thought = str(data.get("thought") or "")
    action = data.get("action", data.get("name"))
    args = data.get("action_input", data.get("arguments", data.get("parameters")))
    if action == FINAL:
        return thought, [], str(data.get("final_answer") or thought).strip()
    if isinstance(action, str) and (tool_names is None or action in tool_names):
        return thought, [ToolCall(name=action, arguments=dict(args or {}))], None
    return "", [], None


_KWARG = re.compile(r"""(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[-\w.]+)""")


def python_style_call(content: str, tool_names: set[str] | None) -> list[ToolCall]:
    """``tool(arg="x")`` written in prose, which llama3.2:3b does instead of a tool call."""
    for name in sorted(tool_names or ()):
        found = re.search(rf"{re.escape(name)}\((.*?)\)", content, re.S)
        if not found:
            continue
        args: dict[str, Any] = {}
        for key, raw in _KWARG.findall(found.group(1)):
            try:
                args[key] = ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                args[key] = raw
        return [ToolCall(name=name, arguments=args)]
    return []


def text_calls(content: str, names: set[str]) -> list[ToolCall]:
    return calls_in_text(content, names)[1] or python_style_call(content, names)


def already_made(call: ToolCall, messages: list[ChatMessage], names: set[str]) -> bool:
    for m in messages:
        if m.role != "assistant":
            continue
        earlier = m.tool_calls or text_calls(m.content, names)
        if any(c.name == call.name and c.arguments == call.arguments for c in earlier):
            return True
    return False
