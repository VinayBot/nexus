"""What tournament solvers and reviewers must return (schema-constrained), and the
line-range edit format: small models rewrite numbered lines far more reliably than they
copy code, so NEXUS turns their edit into the exact search/replace patch."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field


class AnswerOut(BaseModel):
    answer: str = Field(description="Your complete answer.")
    rationale: str = Field(default="", description="Why this answer is right, briefly.")


class CodeOut(BaseModel):
    """Line-range edit: small models rewrite lines far more reliably than they copy them."""

    rationale: str = Field(description="Root cause and why this edit fixes it.")
    file: str = Field(description="Which of the shown files to edit.")
    start_line: int = Field(ge=1, description="First line number to replace.")
    end_line: int = Field(
        ge=1, description="Last line number to replace (same as start for one line)."
    )
    replacement: str = Field(
        description="The new full lines that replace that range, with indentation."
    )


class ReviewItem(BaseModel):
    label: str
    correctness: float = Field(ge=0, le=10)
    risk: float = Field(ge=0, le=10, description="10 = very risky")
    simplicity: float = Field(ge=0, le=10)
    completeness: float = Field(ge=0, le=10)
    reason: str = Field(description="One or two sentences.")


class ReviewBatch(BaseModel):
    reviews: list[ReviewItem]


class Revision(BaseModel):
    decision: Literal["defend", "revise"]
    rationale: str
    answer: str | None = None
    file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    replacement: str | None = None


_NUMBERED = re.compile(r"^\s*\d+\s*\|\s?")


def line_patch(
    files: dict[str, str], file: str, start: int, end: int, replacement: str
) -> dict[str, Any]:
    """Turn a line-range edit into the exact search/replace patch the grounder applies."""
    if file not in files:
        file = next(iter(files), file)
    lines = files.get(file, "").splitlines()
    start, end = min(start, end), max(start, end)
    if not lines or start > len(lines):
        return {"file": file, "search": "", "replace": replacement, "lines": [start, end]}
    end = min(end, len(lines))
    # models sometimes echo the " 12| " prefixes we show them
    cleaned = "\n".join(_NUMBERED.sub("", ln) for ln in replacement.strip("\n").splitlines())
    return {
        "file": file,
        "search": "\n".join(lines[start - 1 : end]),
        "replace": cleaned,
        "lines": [start, end],
    }


def numbered(content: str) -> str:
    return "\n".join(f"{i:3d}| {line}" for i, line in enumerate(content.splitlines(), 1))
