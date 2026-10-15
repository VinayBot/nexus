"""Shared base for playbooks whose decision is a code patch (Self-Healing, Ticket Solver).

Every proposal is applied to the mission workspace copy with tolerant
search/replace and the full test suite (including any reproduction / acceptance
test written during preparation) runs in the sandbox. Validation = the winner's
grounded tests pass.
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from nexus.core.services import services
from nexus.graph.schemas import ValidationResult
from nexus.playbooks.base import Playbook
from nexus.playbooks.patching import apply_search_replace, unified_diff


def winner_of(state: dict[str, Any]) -> dict[str, Any] | None:
    verdict = state.get("verdict") or {}
    proposal: dict[str, Any] | None = (state.get("proposals") or {}).get(verdict.get("winner", ""))
    return proposal


def _failed(summary: str) -> dict[str, Any]:
    return {
        "ok": False,
        "applied": False,
        "passed": 0,
        "failed": 0,
        "errors": 1,
        "summary": summary,
        "backend": "-",
    }


class CodeFixPlaybook(Playbook):
    tournament_mode: ClassVar[Literal["answer", "code"] | None] = "code"

    async def ground(self, proposal: dict[str, Any], tstate: dict[str, Any]) -> dict[str, Any]:
        mission_id = tstate["mission_id"]
        patch = proposal.get("patch") or {}
        file = str(patch.get("file", ""))
        try:
            path = services().workspaces.resolve(mission_id, file)
        except PermissionError as exc:
            return {
                "ok": False,
                "applied": False,
                "passed": 0,
                "failed": 0,
                "errors": 1,
                "summary": str(exc),
                "backend": "-",
            }
        if not path.is_file():
            return {
                "ok": False,
                "applied": False,
                "passed": 0,
                "failed": 0,
                "errors": 1,
                "summary": f"no such file {file}",
                "backend": "-",
            }
        original = path.read_text()
        res = apply_search_replace(
            original, str(patch.get("search", "")), str(patch.get("replace", ""))
        )
        if not res.ok:
            return {
                "ok": False,
                "applied": False,
                "passed": 0,
                "failed": 0,
                "errors": 1,
                "summary": f"patch did not apply: {res.reason}",
                "backend": "-",
            }
        run = await services().sandbox.run_tests(
            services().workspaces.path_for(mission_id), "tests", files={file: res.content}
        )
        from nexus.agents import reputation

        if proposal["solver_id"] != "fix_library":
            await reputation.bump(
                proposal["solver_id"], tests_run=1, tests_passed=1 if run.ok else 0
            )
        return {
            **run.as_dict(),
            "applied": True,
            "strategy": res.strategy,
            "diff": unified_diff(file, original, res.content),
        }

    async def validate(self, state: dict[str, Any]) -> ValidationResult:
        winner = winner_of(state)
        tests = (winner or {}).get("tests") or {}
        if not winner:
            return ValidationResult(ok=False, summary="No winning patch.")
        if not tests.get("applied"):
            return ValidationResult(
                ok=False,
                summary="Winning patch did not apply.",
                details=tests.get("summary", ""),
                tests=tests,
            )
        if not tests.get("ok"):
            fails = "\n".join(tests.get("failures") or [])
            return ValidationResult(
                ok=False,
                summary=f"Tests still fail: {tests.get('summary')}",
                details=fails[:1500],
                tests=tests,
            )
        return ValidationResult(
            ok=True, summary=f"All tests pass with the fix: {tests.get('summary')}", tests=tests
        )
