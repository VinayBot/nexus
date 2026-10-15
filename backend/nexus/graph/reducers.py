"""Custom LangGraph reducers for ``MissionState``.

A reducer decides how a channel combines the value already in state (``left``)
with an update returned by a node (``right``). They matter most when several
nodes run in the same super-step (parallel ``Send`` workers): without a reducer
LangGraph would raise on concurrent writes to one key.

All reducers here are pure and total (``None`` on either side is handled), so
LangGraph can replay them deterministically from checkpoints. The instrumentation
wrapper (``graph/instrument.py``) emits a ``reducer.merged`` event for each update
so the UI can highlight which reducer merged what — reducers themselves never emit.
"""

from __future__ import annotations

from typing import Any

#: Sentinel key: an update ``{RESET: True, ...}`` clears the channel before merging.
RESET = "__reset__"


def merge_dict(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Merge dicts keyed by id (e.g. ``proposals`` keyed by solver id).

    * keys in ``right`` overwrite keys in ``left`` (a solver revising its proposal);
    * a key whose value is ``None`` is deleted;
    * ``{"__reset__": True}`` in ``right`` starts from an empty dict (new tournament).
    """
    right = right or {}
    base: dict[str, Any] = {} if right.get(RESET) else dict(left or {})
    for key, value in right.items():
        if key == RESET:
            continue
        if value is None:
            base.pop(key, None)
        else:
            base[key] = value
    return base


def merge_scores(
    left: dict[str, Any] | None, right: dict[str, Any] | None
) -> dict[str, dict[str, Any]]:
    """Merge peer-review score cards keyed by proposal id.

    Each card is ``{"proposal_id": str, "reviews": [review, ...]}``. Reviews from
    different reviewers accumulate; a second review by the *same* reviewer (a new
    debate round) replaces that reviewer's earlier one. Supports ``__reset__``.
    """
    right = right or {}
    out: dict[str, dict[str, Any]] = (
        {} if right.get(RESET) else {k: dict(v) for k, v in (left or {}).items()}
    )
    for pid, card in right.items():
        if pid == RESET or card is None:
            continue
        existing = out.get(pid, {"proposal_id": pid, "reviews": []})
        by_reviewer = {r["reviewer"]: r for r in existing.get("reviews", [])}
        for review in card.get("reviews", []):
            by_reviewer[review["reviewer"]] = review
        out[pid] = {"proposal_id": pid, "reviews": list(by_reviewer.values())}
    return out


def dedupe_append(
    left: list[dict[str, Any]] | None, right: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    """Append evidence items, skipping any whose ``hash`` is already present.

    Parallel workers often attach the same log excerpt or test report; the hash
    (computed from kind + content) keeps the evidence pack free of duplicates.
    """
    out = list(left or [])
    seen = {item.get("hash") for item in out}
    for item in right or []:
        h = item.get("hash")
        if h and h in seen:
            continue
        seen.add(h)
        out.append(item)
    return out


def sum_counts(left: dict[str, int] | None, right: dict[str, int] | None) -> dict[str, int]:
    """Add per-key counters (retry counts, cycle iterations) from parallel updates.

    A negative value resets that counter to zero (e.g. a new plan revision).
    """
    out = dict(left or {})
    for key, delta in (right or {}).items():
        out[key] = 0 if delta < 0 else out.get(key, 0) + delta
    return out


def append_list(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    """``operator.add`` that tolerates ``None`` (used for ``findings``)."""
    return [*(left or []), *(right or [])]


#: channel -> reducer name, used by the instrumentation and the State Inspector legend.
REDUCED_CHANNELS: dict[str, str] = {
    "messages": "add_messages",
    "findings": "operator.add",
    "proposals": "merge_dict",
    "scores": "merge_scores",
    "evidence": "dedupe_append",
    "retry_counts": "sum_counts",
    "loops": "sum_counts",
    "step_results": "merge_dict",
}
