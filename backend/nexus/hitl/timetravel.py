"""Time travel over a mission's checkpoint history.

* **history** — every checkpoint of the mission's thread as a tree (parent links),
  with step, writer node, next nodes and which branch it belongs to.
* **state_at** — the full state at any checkpoint.
* **rerun** — continue execution from an old checkpoint (LangGraph replays from there).
* **fork** — ``update_state`` at an old checkpoint with a patch (creating a new
  child checkpoint, i.e. a branch), then run that branch.
* **compare** — two branch heads side by side (outcome, tokens, steps, verdict…).
* **choose_runner_up** — a fork that swaps the tournament winner for the runner-up.
"""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import StateSnapshot
from sqlalchemy import select

from nexus.core.event_types import TimetravelFork
from nexus.core.events import emit
from nexus.db import repo
from nexus.db.models import BranchRow
from nexus.graph.runner import MissionRunner


class TimeTravelError(RuntimeError):
    pass


def _cid(config: RunnableConfig | None) -> str | None:
    return ((config or {}).get("configurable") or {}).get("checkpoint_id")


def _summary(snap: StateSnapshot, writer: str | None = None) -> dict[str, Any]:
    """``writer`` = the node that produced this checkpoint (its parent's ``next``)."""
    meta = snap.metadata or {}
    values = snap.values if isinstance(snap.values, dict) else {}
    return {
        "checkpoint_id": _cid(snap.config),
        "parent_id": _cid(snap.parent_config),
        "step": meta.get("step"),
        "source": meta.get("source"),
        "writer": writer or ("__input__" if meta.get("source") == "input" else None),
        "next": list(snap.next),
        "created_at": snap.created_at,
        "interrupted": bool(snap.interrupts),
        "outcome": values.get("outcome"),
        "has_verdict": bool(values.get("verdict")),
        "plan_revision": (values.get("plan") or {}).get("revision"),
    }


class TimeTravel:
    def __init__(self, runner: MissionRunner) -> None:
        self.runner = runner
        self.graph = runner.graph
        self.db = runner.db

    async def _snapshots(self, mission_id: str) -> list[StateSnapshot]:
        return [s async for s in self.graph.aget_state_history(self.runner.config(mission_id))]

    @staticmethod
    def _writers(snaps: list[StateSnapshot]) -> dict[str | None, str | None]:
        """checkpoint id -> node(s) that wrote it, derived from the parent's ``next``."""
        nxt = {_cid(s.config): ",".join(s.next) or None for s in snaps}
        out: dict[str | None, str | None] = {}
        for s in snaps:
            source = (s.metadata or {}).get("source")
            parent = _cid(s.parent_config)
            out[_cid(s.config)] = (
                "update" if source == "update" else nxt.get(parent) if parent else None
            )
        return out

    async def history(self, mission_id: str) -> dict[str, Any]:
        snaps = await self._snapshots(mission_id)
        writers = self._writers(snaps)
        nodes = [_summary(s, writers.get(_cid(s.config))) for s in snaps]  # newest first
        children: dict[str | None, list[str]] = {}
        for n in nodes:
            children.setdefault(n["parent_id"], []).append(n["checkpoint_id"])
        leaves = [n["checkpoint_id"] for n in nodes if n["checkpoint_id"] not in children]
        by_id = {n["checkpoint_id"]: n for n in nodes}
        # assign each checkpoint to the branch of the newest leaf whose lineage contains it
        branch_of: dict[str, str] = {}
        async with self.db.session() as s:
            res = await s.execute(select(BranchRow).where(BranchRow.mission_id == mission_id))
            fork_labels = {r.fork_checkpoint_id: r.label for r in res.scalars()}
        branches = []
        for leaf in sorted(leaves, key=lambda c: by_id[c]["created_at"] or ""):
            lineage = self._lineage(by_id, leaf)
            label = next((fork_labels[c] for c in lineage if c in fork_labels), "main")
            for cid in lineage:
                branch_of.setdefault(cid, leaf)
            branches.append(
                {
                    "head": leaf,
                    "label": label,
                    "length": len(lineage),
                    "outcome": by_id[leaf]["outcome"],
                }
            )
        for n in nodes:
            n["branch"] = branch_of.get(n["checkpoint_id"])
        return {"checkpoints": list(reversed(nodes)), "branches": branches}

    @staticmethod
    def _lineage(by_id: dict[str, dict[str, Any]], leaf: str) -> list[str]:
        out = []
        cur: str | None = leaf
        while cur is not None and cur in by_id:
            out.append(cur)
            cur = by_id[cur]["parent_id"]
        return out

    async def state_at(self, mission_id: str, checkpoint_id: str) -> dict[str, Any]:
        snap = await self.graph.aget_state(self.runner.config(mission_id, checkpoint_id))
        if not snap.values:
            raise TimeTravelError("checkpoint not found")
        writer = None
        source = (snap.metadata or {}).get("source")
        if source == "update":
            writer = "update"
        elif snap.parent_config:
            parent = await self.graph.aget_state(snap.parent_config)
            writer = ",".join(parent.next) or None
        return {"summary": _summary(snap, writer), "values": snap.values}

    def _ensure_idle(self, mission_id: str) -> None:
        if self.runner.is_running(mission_id):
            raise TimeTravelError("mission is running; cancel it or wait before time-travelling")

    async def rerun(self, mission_id: str, checkpoint_id: str) -> None:
        self._ensure_idle(mission_id)
        await repo.audit(
            self.db,
            actor="owner",
            channel="ui",
            action="timetravel.rerun",
            mission_id=mission_id,
            detail={"checkpoint_id": checkpoint_id},
        )
        self.runner.start(mission_id, None, resumed=True, checkpoint_id=checkpoint_id)

    async def fork(
        self,
        mission_id: str,
        checkpoint_id: str,
        patch: dict[str, Any],
        *,
        as_node: str | None = None,
        label: str | None = None,
        run: bool = True,
    ) -> dict[str, Any]:
        self._ensure_idle(mission_id)
        base = self.runner.config(mission_id, checkpoint_id)
        snap = await self.graph.aget_state(base)
        if not snap.values:
            raise TimeTravelError("checkpoint not found")
        new_config = await self.graph.aupdate_state(base, patch, as_node=as_node)
        new_cid = _cid(new_config)
        if not new_cid:
            raise TimeTravelError("fork did not produce a checkpoint")
        branch_id = uuid.uuid4().hex[:10]
        label = label or f"fork of {checkpoint_id[-6:]}"
        async with self.db.session() as s:
            s.add(
                BranchRow(
                    id=branch_id,
                    mission_id=mission_id,
                    label=label,
                    fork_checkpoint_id=new_cid,
                    patch=patch,
                )
            )
        await repo.audit(
            self.db,
            actor="owner",
            channel="ui",
            action="timetravel.fork",
            mission_id=mission_id,
            detail={
                "from": checkpoint_id,
                "new": new_cid,
                "patch_keys": sorted(patch),
                "as_node": as_node,
            },
        )
        emit(
            "timetravel.fork",
            TimetravelFork(
                from_checkpoint=checkpoint_id,
                new_checkpoint=new_cid,
                patch_keys=sorted(patch),
                branch_id=branch_id,
            ),
            mission_id=mission_id,
        )
        if run:
            await repo.update_mission(self.db, mission_id, status="running", outcome=None)
            self.runner.start(mission_id, None, resumed=True, checkpoint_id=new_cid)
        return {"branch_id": branch_id, "checkpoint_id": new_cid, "label": label}

    async def choose_runner_up(self, mission_id: str) -> dict[str, Any]:
        """Fork right after the council with the runner-up promoted to winner."""
        snaps = await self._snapshots(mission_id)
        writers = self._writers(snaps)
        for snap in snaps:
            values = snap.values if isinstance(snap.values, dict) else {}
            verdict = values.get("verdict")
            if verdict and verdict.get("runner_up") and writers.get(_cid(snap.config)) == "council":
                runner = verdict["runner_up"]
                proposal = (values.get("proposals") or {}).get(runner)
                if not proposal:
                    break
                labels = {v: k for k, v in (values.get("labels") or {}).items()}
                patched = {
                    **verdict,
                    "winner": runner,
                    "runner_up": verdict["winner"],
                    "winner_label": labels.get(runner, verdict.get("winner_label")),
                    "reasoning": "Owner chose the runner-up via time travel.",
                }
                cid = _cid(snap.config)
                assert cid is not None
                return await self.fork(
                    mission_id,
                    cid,
                    {"verdict": patched, "answer": proposal["content"], "validation": None},
                    as_node="council",
                    label=f"runner-up {runner}",
                )
        raise TimeTravelError("no tournament with a runner-up found in this mission")

    async def compare(self, mission_id: str, head_a: str, head_b: str) -> dict[str, Any]:
        snaps = await self._snapshots(mission_id)
        by_id = {_cid(s.config): s for s in snaps}

        def describe(head: str) -> dict[str, Any]:
            snap = by_id.get(head)
            if snap is None:
                raise TimeTravelError(f"unknown checkpoint {head}")
            lineage = []
            cur: StateSnapshot | None = snap
            while cur is not None:
                lineage.append(cur)
                cur = by_id.get(_cid(cur.parent_config)) if cur.parent_config else None
            v = snap.values if isinstance(snap.values, dict) else {}
            first, last = lineage[-1].created_at, lineage[0].created_at
            return {
                "head": head,
                "steps": len(lineage),
                "outcome": v.get("outcome"),
                "answer": (v.get("answer") or "")[:1200],
                "winner": (v.get("verdict") or {}).get("winner"),
                "confidence": (v.get("verdict") or {}).get("confidence"),
                "risk": (v.get("risk") or {}).get("level"),
                "execution": (v.get("execution") or {}).get("summary"),
                "verification": (v.get("verification") or {}).get("summary"),
                "plan_revision": (v.get("plan") or {}).get("revision"),
                "started": first,
                "finished": last,
                "lineage": [_cid(s.config) for s in reversed(lineage)],
            }

        a, b = describe(head_a), describe(head_b)
        common = None
        for x, y in zip(a["lineage"], b["lineage"], strict=False):
            if x != y:
                break
            common = x
        return {"a": a, "b": b, "fork_point": common}
