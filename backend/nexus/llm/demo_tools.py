"""Small deterministic tools shared by the raw agent and the LangGraph agent comparison."""

from __future__ import annotations

import ast
import operator
import re
from typing import Any

from nexus.llm.raw_react_agent import RawTool
from nexus.llm.types import ToolSpec

_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calculator(expression: str) -> str:
    """Evaluate arithmetic safely (numbers and + - * / // % ** only)."""

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            right = ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 12:
                raise ValueError("exponent too large")
            return float(_OPS[type(node.op)](ev(node.left), right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return float(_OPS[type(node.op)](ev(node.operand)))
        raise ValueError(f"unsupported expression: {ast.dump(node)[:60]}")

    # small models write 2^10, 3 x 4 and 1,000: accept the usual notations
    text = str(expression).replace("^", "**").replace("×", "*").replace(",", "")
    text = re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", "*", text)
    try:
        value = ev(ast.parse(text, mode="eval").body)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(
            f"{exc}. Pass only numbers and + - * / ** ( ), e.g. '(144 / 12) ** 2 - 40'; "
            "use the other tools for words and facts first."
        ) from exc
    return str(int(value)) if value == int(value) else f"{value:.6g}"


def count_letters(word: str) -> str:
    return str(sum(ch.isalpha() for ch in str(word)))


NEXUS_FACTS = {
    "commander": "The Commander is the supervisor robot that routes work to the squad.",
    "command center floor": "The Mission Floor is the live animated view of a mission.",
    "solvers": "Blaze, Volt and Frost are tournament solvers with different fix strategies.",
    "forge": "Forge the engineer writes code patches.",
    "squad size": "The default squad has 14 robots.",
}


def lookup_fact(topic: str) -> str:
    key = str(topic).lower().strip()
    for k, v in NEXUS_FACTS.items():
        if k in key or key in k:
            return v
    return f"No fact found for '{topic}'. Known topics: {', '.join(NEXUS_FACTS)}"


RAW_TOOLS = [
    RawTool(
        "calculator",
        "Evaluate an arithmetic expression.",
        {"expression": "e.g. '17 * 23 + 4'"},
        calculator,
    ),
    RawTool("count_letters", "Count the letters in a word.", {"word": "the word"}, count_letters),
    RawTool(
        "lookup_fact",
        "Look up a fact about the NEXUS command center.",
        {"topic": "topic name"},
        lookup_fact,
    ),
]

TOOL_SPECS = [
    ToolSpec(
        name="calculator",
        description="Evaluate an arithmetic expression.",
        parameters={
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    ),
    ToolSpec(
        name="count_letters",
        description="Count the letters in a word.",
        parameters={
            "type": "object",
            "properties": {"word": {"type": "string"}},
            "required": ["word"],
        },
    ),
    ToolSpec(
        name="lookup_fact",
        description="Look up a fact about the NEXUS command center.",
        parameters={
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    ),
]

TOOL_FNS = {"calculator": calculator, "count_letters": count_letters, "lookup_fact": lookup_fact}

COMPARE_TASKS = [
    "What is 17 * 23 plus the number of letters in the word 'android'?",
    "How many robots are in the default squad, multiplied by 3?",
    "What is (144 / 12) to the power of 2, minus 40?",
]
