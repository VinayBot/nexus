"""Tolerant JSON extraction from model output.

Small models wrap JSON in prose or code fences, use single quotes, Python
literals, trailing commas, or stop before closing brackets. ``extract_json``
tries strict parsing first and only then applies increasingly forgiving repairs.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")
_PY_LITERALS = {r"\bTrue\b": "true", r"\bFalse\b": "false", r"\bNone\b": "null"}


class JsonRepairError(ValueError):
    pass


def _balanced_candidates(text: str) -> list[str]:
    """Every top-level {...} or [...] span, scanning with a string-aware bracket stack."""
    out: list[str] = []
    stack: list[str] = []
    start = -1
    in_str = False
    esc = False
    quote = ""
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
            continue
        if ch in "\"'" and stack:
            in_str, quote = True, ch
        elif ch in "{[":
            if not stack:
                start = i
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack and ch == stack[-1]:
            stack.pop()
            if not stack and start >= 0:
                out.append(text[start : i + 1])
                start = -1
    if stack and start >= 0:  # truncated output: close what is open
        tail = text[start:]
        if in_str:
            tail += quote
        out.append(tail + "".join(reversed(stack)))
    return out


def _repair(s: str) -> str:
    s = s.strip()
    s = _TRAILING_COMMA.sub(r"\1", s)
    for pat, rep in _PY_LITERALS.items():
        s = re.sub(pat, rep, s)
    if "'" in s and '"' not in s:
        s = s.replace("'", '"')
    # unquoted keys: {key: 1} -> {"key": 1}
    s = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", r'\1"\2"\3', s)
    return s


def extract_json(text: str) -> Any:
    """Return the first JSON value found in ``text``; raise JsonRepairError if none."""
    if not text or not text.strip():
        raise JsonRepairError("empty model output")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    sources = [m.group(1) for m in _FENCE.finditer(text)] + [text]
    for source in sources:
        for cand in _balanced_candidates(source):
            for attempt in (cand, _repair(cand)):
                try:
                    return json.loads(attempt)
                except json.JSONDecodeError:
                    continue
    raise JsonRepairError(f"no JSON object found in output: {text[:160]!r}")
