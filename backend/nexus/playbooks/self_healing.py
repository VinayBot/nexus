"""Self-Healing Pipeline (flagship).

Hawk spots an incident → prepare (workspace, reproduction, suspects, memory) →
parallel investigation (logs · code · Fix Library) → solution tournament with
every patch grounded in its own sandbox → evidence → risk gate (HIGH: dry-run +
approval, emailed to the owner) → apply on a fix branch with hot reload →
verify on live traffic → automatic rollback + replan on failure → Fix Library.
"""

from __future__ import annotations

import asyncio
from typing import Any

from nexus.core.services import services
from nexus.db.models import IncidentRow
from nexus.graph.schemas import (
    EvidenceItem,
    ExecutionResult,
    Plan,
    PlanStep,
    ProposedAction,
    VerificationResult,
)
from nexus.playbooks.base import TournamentBrief, findings_text
from nexus.playbooks.code_fix import CodeFixPlaybook, winner_of
from nexus.playbooks.healing_prep import candidate_files, focus_line, recall_fix, reproduce
from nexus.playbooks.patching import apply_search_replace, diff_size, unified_diff
from nexus.playbooks.watcher import error_digest

TOOLS = {
    "watcher": ["observability.health", "observability.read_logs", "observability.metrics"],
    "coder": ["workspace.read_file", "workspace.search", "workspace.list_files"],
    "researcher": ["knowledge.search"],
}


class SelfHealing(CodeFixPlaybook):
    id = "self_healing"
    title = "Self-Healing Pipeline"
    description = "Detect, reproduce, fix (tournament), approve, apply, verify, roll back, learn."
    planner_hint = (
        "This is a production incident on the demo-service. Plan 2-3 PARALLEL investigation "
        "steps with no dependencies: one 'watcher' step reading health and error logs, one "
        "'coder' step reading the suspect source files, one 'researcher' step searching the "
        "Fix Library for similar incidents. The fix itself is chosen by a tournament later."
    )

    # -- preparation ------------------------------------------------------------------
    async def prepare(self, state: dict[str, Any]) -> dict[str, Any]:
        svc = services()
        demo = svc.demo
        inputs = dict(state.get("inputs") or {})
        mission_id = state["mission_id"]
        incident = None
        if inputs.get("incident_id"):
            async with svc.db.session() as s:
                incident = await s.get(IncidentRow, inputs["incident_id"])
        if incident is not None:
            signal, digest = incident.signal, incident.detail
        else:  # manual mission: read the service now
            h = await demo.health()
            signal = (
                f"demo-service {h.get('status')}: error rate {float(h.get('error_rate') or 0):.0%}"
            )
            digest = error_digest(await demo.logs(80))
        ws = svc.workspaces.copy_from(demo.live, mission_id)
        suspects = candidate_files(ws, digest)
        files = {f: (ws / f).read_text() for f in suspects}
        repro = await reproduce(mission_id, inputs.get("incident_id") or mission_id, digest, files)
        suspects = candidate_files(ws, digest, "\n".join(repro["existing"].get("failures") or []))
        files = {f: (ws / f).read_text() for f in suspects}
        prior = await recall_fix(signal, digest, files, mission_id)
        inputs.update(
            focus=focus_line(ws, digest),
            signal=signal,
            digest=digest[:4000],
            suspects=suspects,
            repro=repro,
            prior_fix={k: v for k, v in prior.items() if k != "proposal"} if prior else None,
            seed=prior["proposal"]
            if prior and (prior["proposal"]["tests"] or {}).get("ok")
            else None,
        )
        ex = repro["existing"]
        evidence = [
            EvidenceItem(
                kind="log", title=f"Error digest — {signal}", content=digest[:3000]
            ).with_hash(),
            EvidenceItem(
                kind="test_report",
                title="Reproduction on the buggy code",
                content=f"Existing tests: {ex.get('summary')}\n"
                + "\n".join(ex.get("failures") or [])
                + (
                    f"\nRepro test {repro['repro_test']} fails as expected."
                    if repro.get("repro_test")
                    else f"\n{repro.get('repro_rejected', 'No reproduction test kept.')}"
                ),
            ).with_hash(),
        ]
        return {"inputs": inputs, "evidence": [e.model_dump() for e in evidence]}

    def default_tools(self, role: str) -> list[str] | None:
        return TOOLS.get(role)

    def template_plan(self, state: dict[str, Any]) -> Plan:
        suspects = ", ".join((state.get("inputs") or {}).get("suspects") or ["app/orders.py"])
        return Plan(
            goal="Restore the demo-service to healthy with a verified fix",
            source="template",
            steps=[
                PlanStep(
                    id="logs",
                    title="Read health and error logs",
                    role="watcher",
                    description="Read the service health and the recent ERROR logs; summarise what fails, where and how often.",
                    success_criteria="Failure mode and location identified.",
                    tools=TOOLS["watcher"],
                ),
                PlanStep(
                    id="code",
                    title="Inspect suspect code",
                    role="coder",
                    description=f"Read {suspects} and explain the most likely root cause of the errors.",
                    success_criteria="Root cause hypothesis with file and line.",
                    tools=TOOLS["coder"],
                ),
                PlanStep(
                    id="history",
                    title="Search the Fix Library",
                    role="researcher",
                    description="Search the Fix Library for similar past incidents and how they were fixed.",
                    success_criteria="Similar incidents listed, or none found.",
                    tools=TOOLS["researcher"],
                ),
            ],
        )

    # -- tournament ---------------------------------------------------------------------
    def tournament_brief(self, state: dict[str, Any]) -> TournamentBrief:
        inputs = state.get("inputs") or {}
        ws = services().workspaces.path_for(state["mission_id"])
        focus = inputs.get("focus")
        # with a precise traceback, show only the failing file: small models get lost in more
        shown = [focus["file"]] if focus else (inputs.get("suspects") or [])
        files = {f: (ws / f).read_text() for f in shown if (ws / f).exists()}
        repro = inputs.get("repro") or {}
        failures = "\n".join((repro.get("existing") or {}).get("failures") or [])
        context = findings_text(state, 2500)
        if inputs.get("prior_fix"):
            context += (
                f"\nThe Fix Library has a similar past incident: {inputs['prior_fix']['title']}"
            )
        seeds = {"fix_library": inputs["seed"]} if inputs.get("seed") else {}
        return TournamentBrief(
            mode="code",
            topic="self_healing",
            question=(
                f"Production incident: {inputs.get('signal')}\n\nError report:\n{str(inputs.get('digest', ''))[:2500]}\n\n"
                f"Failing tests:\n{failures or '(none)'}\n\nFind the bug and fix it with one small edit."
            ),
            context=context,
            code_context={"files": files, "focus": inputs.get("focus")},
            # memory hit → one solver races the remembered fix instead of three
            solvers=["volt"] if seeds else ["blaze", "volt", "frost"],
            max_rounds=0 if seeds else 1,
            seed_proposals=seeds,
        )

    # -- acting --------------------------------------------------------------------------
    def proposed_action(self, state: dict[str, Any]) -> ProposedAction:
        winner = winner_of(state) or {}
        patch = winner.get("patch") or {}
        diff = (winner.get("tests") or {}).get("diff", "")
        return ProposedAction(
            kind="apply_patch",
            summary=f"Apply {winner.get('strategy', 'fix')} to {patch.get('file')} on the live demo-service",
            target="demo-service",
            files_touched=[str(patch.get("file", ""))],
            diff_lines=diff_size(diff),
            blast_radius="service",
            payload={"patch": patch, "diff": diff},
        )

    def _patched(self, state: dict[str, Any], base: str) -> tuple[str, str, str]:
        patch = (state.get("action") or {}).get("payload", {}).get("patch") or {}
        file = str(patch["file"])
        res = apply_search_replace(base, str(patch["search"]), str(patch["replace"]))
        if not res.ok:
            raise ValueError(f"patch no longer applies: {res.reason}")
        return file, res.content, unified_diff(file, base, res.content)

    async def dry_run(self, state: dict[str, Any]) -> ExecutionResult:
        demo = services().demo
        patch = (state.get("action") or {}).get("payload", {}).get("patch") or {}
        try:
            file, content, _ = self._patched(state, demo.read(str(patch.get("file"))))
        except (ValueError, KeyError, OSError) as exc:
            return ExecutionResult(ok=False, summary=f"Dry run failed: {exc}", dry_run=True)
        ws = services().workspaces.copy_from(demo.live, f"{state['mission_id']}-dry")
        run = await services().sandbox.run_tests(ws, "tests", files={file: content})
        return ExecutionResult(
            ok=run.ok,
            summary=f"Patch on a fresh copy of live code: {run.as_dict()['summary']}",
            details=run.as_dict(),
            dry_run=True,
        )

    async def execute(self, state: dict[str, Any]) -> ExecutionResult:
        demo = services().demo
        patch = (state.get("action") or {}).get("payload", {}).get("patch") or {}
        try:
            file, content, diff = self._patched(state, demo.read(str(patch.get("file"))))
            info = await demo.apply_fix(
                state["mission_id"],
                file,
                content,
                f"nexus: fix {(state.get('inputs') or {}).get('incident_id', state['mission_id'])}",
            )
        except Exception as exc:
            return ExecutionResult(ok=False, summary=f"Could not apply: {exc}")
        return ExecutionResult(
            ok=True,
            summary=f"Applied to {file} on branch {info['branch']} ({info['commit']}); service reloading",
            details={**info, "file": file, "diff": diff},
        )

    async def verify(self, state: dict[str, Any]) -> VerificationResult:
        """Watch live traffic: no new errors and orders flowing for the verify window."""
        demo = services().demo
        window = services().settings.verify_window_s
        await asyncio.sleep(3)  # uvicorn --reload restart
        before = await demo.metrics()
        observations: list[str] = []
        statuses: list[str] = []
        elapsed = 0.0
        while elapsed < window:
            await asyncio.sleep(1)
            elapsed += 1
            h = await demo.health()
            statuses.append(str(h.get("status")))
        after = await demo.metrics()
        if not before or not after:
            return VerificationResult(
                ok=False,
                summary="Service unreachable after the change.",
                observations=statuses[-5:],
            )
        new_errors = int(after.get("errors", 0)) - int(before.get("errors", 0))
        processed = int(after.get("orders_processed", 0)) - int(before.get("orders_processed", 0))
        if after.get("started_at") != before.get("started_at"):
            observations.append("service restarted during the window")
        observations.append(
            f"{processed} orders processed, {new_errors} new errors in {window:.0f}s"
        )
        ok = new_errors == 0 and processed > 0
        summary = (
            "Healthy on live traffic"
            if ok
            else ("Errors continue after the fix" if new_errors else "No traffic processed")
        )
        return VerificationResult(
            ok=ok,
            summary=f"{summary}: {observations[-1]}",
            observations=observations + statuses[-5:],
        )

    async def rollback(self, state: dict[str, Any]) -> ExecutionResult:
        details = (state.get("execution") or {}).get("details") or {}
        if not details.get("branch"):
            return ExecutionResult(ok=True, summary="Nothing was applied; nothing to roll back.")
        await services().demo.rollback(details["previous"], details["branch"])
        return ExecutionResult(
            ok=True, summary=f"Rolled back {details['branch']} → {details['previous']}"
        )

    async def remember(self, state: dict[str, Any]) -> list[str]:
        svc = services()
        details = (state.get("execution") or {}).get("details") or {}
        if details.get("branch"):
            await svc.demo.promote(details["branch"])
        memory = svc.extras.get("memory")
        winner = winner_of(state) or {}
        patch = winner.get("patch") or {}
        inputs = state.get("inputs") or {}
        if memory is None or not patch:
            return []
        chaos = None
        if inputs.get("incident_id"):
            async with svc.db.session() as s:
                row = await s.get(IncidentRow, inputs["incident_id"])
                chaos = row.chaos if row else None
        verdict = state.get("verdict") or {}
        text = (
            f"Incident: {inputs.get('signal')}\nSymptoms:\n{str(inputs.get('digest', ''))[:900]}\n"
            f"Root cause: {verdict.get('reasoning') or winner.get('rationale', '')}\n"
            f"Fix in {patch.get('file')}:\n{details.get('diff') or (winner.get('tests') or {}).get('diff', '')}"
        )
        doc_id = await memory.add(
            "fix_library",
            text,
            {
                "title": f"Fix: {inputs.get('signal', 'incident')}"[:120],
                "incident_id": inputs.get("incident_id") or "",
                "mission_id": state["mission_id"],
                "file": patch.get("file", ""),
                "search": patch.get("search", ""),
                "replace": patch.get("replace", ""),
                "root_cause": str(verdict.get("reasoning") or winner.get("rationale", ""))[:500],
                "chaos": chaos or "",
                "winner": verdict.get("winner", ""),
            },
        )
        return [doc_id]

    def report_extras(self, state: dict[str, Any]) -> dict[str, Any]:
        inputs = state.get("inputs") or {}
        winner = winner_of(state) or {}
        return {
            "incident_id": inputs.get("incident_id"),
            "signal": inputs.get("signal"),
            "diff": (state.get("execution") or {}).get("details", {}).get("diff")
            or (winner.get("tests") or {}).get("diff"),
            "tests": {
                k: (winner.get("tests") or {}).get(k)
                for k in ("passed", "failed", "errors", "backend")
            },
            "memory_assisted": bool(inputs.get("seed")),
        }
