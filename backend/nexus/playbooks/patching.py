"""Search/replace patching that tolerates small-model sloppiness.

Models are asked for an exact ``search`` block copied from the file and a
``replace`` block. 3–8B models frequently get indentation or trailing whitespace
slightly wrong, so matching tries, in order:

1. exact substring (must be unique);
2. line-by-line match ignoring surrounding whitespace, then the replacement is
   re-indented by the indentation difference;
3. a single non-blank search line matched after stripping (unique).

Anything ambiguous or not found is rejected with a reason — never guessed.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass


@dataclass
class PatchResult:
    ok: bool
    content: str
    reason: str = ""
    strategy: str = ""


def _indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _reindent(replace: str, model_indent: str, file_indent: str) -> str:
    """Rebase the model's indentation onto the file's (relative nesting is kept)."""
    out = []
    for line in replace.splitlines():
        if not line.strip():
            out.append("")
        elif line.startswith(model_indent):
            out.append(file_indent + line[len(model_indent) :])
        else:
            out.append(file_indent + line.lstrip())
    return "\n".join(out)


def apply_search_replace(content: str, search: str, replace: str) -> PatchResult:
    search = search.strip("\n")
    replace = replace.strip("\n")
    if not search.strip():
        return PatchResult(False, content, "empty search block")
    if search == replace:
        return PatchResult(False, content, "search and replace are identical (no change)")

    count = content.count(search)
    if count == 1:
        return PatchResult(True, content.replace(search, replace, 1), strategy="exact")
    if count > 1:
        return PatchResult(
            False, content, f"search block matches {count} places; include more context"
        )

    lines = content.splitlines()
    s_lines = search.splitlines()
    while s_lines and not s_lines[0].strip():
        s_lines.pop(0)
    n = len(s_lines)
    stripped = [line.strip() for line in s_lines]
    matches = [
        i for i in range(len(lines) - n + 1) if [x.strip() for x in lines[i : i + n]] == stripped
    ]
    if len(matches) == 1:
        i = matches[0]
        file_indent = _indent(lines[i])
        model_indent = _indent(s_lines[0])
        new_block = _reindent(replace, model_indent, file_indent)
        new_lines = lines[:i] + new_block.splitlines() + lines[i + n :]
        return PatchResult(
            True,
            "\n".join(new_lines) + ("\n" if content.endswith("\n") else ""),
            strategy="whitespace-tolerant",
        )
    if len(matches) > 1:
        return PatchResult(
            False, content, "search block is ambiguous after whitespace normalisation"
        )

    meaningful = [s for s in stripped if s]
    if len(meaningful) == 1:
        idx = [i for i, line in enumerate(lines) if line.strip() == meaningful[0]]
        if len(idx) == 1:
            i = idx[0]
            new_block = _reindent(
                replace, _indent(next(x for x in s_lines if x.strip())), _indent(lines[i])
            )
            new_lines = lines[:i] + new_block.splitlines() + lines[i + 1 :]
            return PatchResult(
                True,
                "\n".join(new_lines) + ("\n" if content.endswith("\n") else ""),
                strategy="single-line",
            )

    close = difflib.get_close_matches(
        stripped[0] if stripped else "", [x.strip() for x in lines], n=1, cutoff=0.6
    )
    hint = f" Closest line in the file: {close[0]!r}" if close else ""
    return PatchResult(False, content, f"search block not found in the file.{hint}")


def unified_diff(path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=2,
        )
    )


def diff_size(diff: str) -> int:
    return sum(
        1 for line in diff.splitlines() if line[:1] in "+-" and not line.startswith(("+++", "---"))
    )
