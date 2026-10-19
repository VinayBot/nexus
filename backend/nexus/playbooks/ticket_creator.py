"""Ticket Creator: "create a ticket for the bug in the pipeline and email it to me".

1. *Investigate* (Echo): read the code the request points at (a copy of the demo
   shop when it is about the shop) and the service's recent error logs.
2. *Draft* (Quill): a structured bug report: title, summary, steps to reproduce,
   expected vs actual, suspected file, severity, labels.
3. *Check*: the draft has a real title, description and at least one step.
4. *File* (Swift): ``tickets.create`` puts it in the tracker as the next T-number.
   Creating a local ticket scores LOW risk, so no approval stop.
5. *Share*: the ticket is emailed to the owner (Settings → Email results), and the
   result card offers "Solve this ticket now" (the Ticket Solver).
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from nexus.core.services import services
from nexus.graph.schemas import (
    ExecutionResult,
    Finding,
    Plan,
    PlanStep,
    ProposedAction,
    ValidationResult,
    VerificationResult,
)
from nexus.llm.types import ChatMessage
from nexus.playbooks.base import Playbook
from nexus.safety.guardrails import fence

DRAFT = "ticket.json"
CODE_WORDS = re.compile(
    r"\b(pipeline|orders?|inventory|config|main|store|api|service|shop)\b", re.I
)
EMAIL_WORDS = re.compile(r"\b(e-?mail|mail|share|send)\b", re.I)


class TicketDraft(BaseModel):
    title: str = Field(
        description="Short, specific title, e.g. 'Pipeline crashes on guest orders'."
    )
    summary: str = Field(description="2-4 sentences: what is wrong and who it affects.")
    steps: list[str] = Field(min_length=1, max_length=6, description="Steps to reproduce.")
    expected: str
    actual: str
    suspected_file: str = Field(default="", description="e.g. app/pipeline.py, or empty.")
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    labels: list[str] = Field(default_factory=lambda: ["bug"], max_length=4)


def draft_markdown(d: TicketDraft, ticket_id: str | None = None) -> str:
    head = f"# {ticket_id + ': ' if ticket_id else ''}{d.title}"
    lines = [
        head,
        f"**Severity:** {d.severity} · **Labels:** {', '.join(d.labels) or '-'}"
        + (f" · **Suspected file:** `{d.suspected_file}`" if d.suspected_file else ""),
        "## Summary",
        d.summary,
        "## Steps to reproduce",
        *[f"{i}. {s}" for i, s in enumerate(d.steps, 1)],
        "## Expected",
        d.expected,
        "## Actual",
        d.actual,
    ]
    return "\n\n".join(lines)


def _files_named(task: str, root: Any) -> list[str]:
    """App files the request names ("bug in pipeline" → app/pipeline.py)."""
    names = {w.lower().rstrip("s") for w in CODE_WORDS.findall(task)}
    files = sorted(str(p.relative_to(root)) for p in root.glob("app/*.py"))
    return [f for f in files if any(n and n in f for n in names)][:2]


class TicketCreator(Playbook):
    id = "ticket_creator"
    title = "Create Ticket"
    description = (
        "Create a new ticket (bug report or task) from a description, after looking at "
        "the code and logs, and email it to the owner."
    )
    tournament_mode = None
    fixed_plan = True

    async def prepare(self, state: dict[str, Any]) -> dict[str, Any]:
        svc = services()
        task = state.get("task", "")
        demo = svc.extras.get("demo")
        ws = svc.workspaces.ensure(state["mission_id"])
        if demo is not None and demo.live.is_dir() and CODE_WORDS.search(task):
            ws = svc.workspaces.copy_from(demo.live, state["mission_id"])
        return {"inputs": {**(state.get("inputs") or {}), "files": _files_named(task, ws)}}

    def template_plan(self, state: dict[str, Any]) -> Plan:
        return Plan(
            goal="Write and file a clear ticket",
            source="template",
            rationale="investigate, then draft",
            steps=[
                PlanStep(
                    id="investigate",
                    title="Read the code and recent errors",
                    description="investigate",
                    role="researcher",
                    success_criteria="Relevant code and log lines collected.",
                ),
                PlanStep(
                    id="draft",
                    title="Draft the ticket",
                    description="draft",
                    role="writer",
                    depends_on=["investigate"],
                    success_criteria="Title, summary, steps, expected and actual written.",
                ),
            ],
        )

    async def _evidence(self, mission_id: str, files: list[str], agent_id: str) -> str:
        svc = services()
        parts = []
        for f in files:
            res = await svc.mcp.call(
                "workspace.read_file", {"path": f}, agent_id=agent_id, allowlist=None
            )
            if res.ok:
                parts.append(fence(res.text[:2500], source=f))
        demo = svc.extras.get("demo")
        if demo is not None:
            from nexus.playbooks.watcher import error_digest

            digest = error_digest(await demo.logs(60))
            if digest != "(no error logs)":
                parts.append(fence(digest[:1500], source="demo-service error logs"))
        ws = svc.workspaces.path_for(mission_id)
        (ws / "evidence.txt").write_text("\n\n".join(parts))
        return "\n\n".join(parts)

    async def run_step(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        svc = services()
        agent_id, step = payload["agent_id"], payload["step"]
        ws = svc.workspaces.path_for(payload["mission_id"])
        if step["description"] == "investigate":
            files = payload["inputs"].get("files") or []
            evidence = await self._evidence(payload["mission_id"], files, agent_id)
            summary = (
                f"Read {', '.join(files) or 'no code files'}; "
                f"{'found error logs' if 'error logs' in evidence else 'no recent errors in the logs'}"
            )
        else:
            evidence = (ws / "evidence.txt").read_text() if (ws / "evidence.txt").exists() else ""
            draft = await svc.llm.structured(
                [
                    ChatMessage.system(
                        "You write clear, specific bug tickets for developers. Base them on the "
                        "evidence; do not invent details the evidence does not support. Leave "
                        "out any request to email or share the ticket."
                    ),
                    ChatMessage.user(
                        f"Request:\n{payload['task']}\n\nEvidence:\n{evidence or '(none)'}"
                    ),
                ],
                TicketDraft,
                purpose="ticket",
                agent_id=agent_id,
                max_tokens=900,
                default=TicketDraft(
                    title=payload["task"][:80],
                    summary=payload["task"],
                    steps=["See the description."],
                    expected="The service works correctly.",
                    actual="See the description.",
                ),
            )
            (ws / DRAFT).write_text(draft.model_dump_json(indent=2))
            summary = f"Drafted '{draft.title}' ({draft.severity})"
        return Finding(
            step_id=step["id"], agent_id=agent_id, summary=summary, ok=True, iterations=1
        ).model_dump()

    def _draft(self, mission_id: str) -> TicketDraft:
        path = services().workspaces.path_for(mission_id) / DRAFT
        return TicketDraft.model_validate_json(path.read_text())

    async def synthesize(self, state: dict[str, Any]) -> dict[str, Any] | None:
        return {"answer": draft_markdown(self._draft(state["mission_id"]))}

    async def validate(self, state: dict[str, Any]) -> ValidationResult:
        try:
            d = self._draft(state["mission_id"])
        except (OSError, ValueError):
            return ValidationResult(ok=False, summary="No ticket draft was written.")
        problems = [
            msg
            for bad, msg in (
                (len(d.title.strip()) < 8, "title too short"),
                (len(d.summary.strip()) < 40, "summary too short"),
                (not any(s.strip() for s in d.steps), "no steps to reproduce"),
            )
            if bad
        ]
        if problems:
            return ValidationResult(
                ok=False, summary="Draft incomplete", details="; ".join(problems)
            )
        return ValidationResult(ok=True, summary=f"Draft complete: '{d.title}'")

    def proposed_action(self, state: dict[str, Any]) -> ProposedAction:
        return ProposedAction(
            kind="create_ticket",
            summary=f"File the ticket '{self._draft(state['mission_id']).title}'",
            blast_radius="local",
        )

    async def execute(self, state: dict[str, Any]) -> ExecutionResult:
        svc = services()
        d = self._draft(state["mission_id"])
        res = await svc.mcp.call(
            "tickets.create",
            {"title": d.title[:200], "body": draft_markdown(d), "labels": d.labels},
            agent_id="swift",
            allowlist=None,
        )
        if not res.ok or not re.fullmatch(r"T-\d+", res.text.strip()):
            return ExecutionResult(ok=False, summary=f"Could not create the ticket: {res.text}")
        ticket_id = res.text.strip()
        details: dict[str, Any] = {"ticket_id": ticket_id}
        notifier = svc.extras.get("notifier")
        to = notifier.prefs().get("to") if notifier else None
        if notifier is not None and to and EMAIL_WORDS.search(state.get("task", "")):
            _, status = await notifier.mailer.send(
                str(to),
                f"[NEXUS] New ticket {ticket_id}: {d.title}"[:250],
                notifier_html(d, ticket_id),
                mission_id=state["mission_id"],
                text=draft_markdown(d, ticket_id),
            )
            details.update(emailed_to=to, email_status=status)
        summary = f"Created {ticket_id}" + (
            f" and emailed it to {to}" if details.get("emailed_to") else ""
        )
        return ExecutionResult(ok=True, summary=summary, details=details)

    async def verify(self, state: dict[str, Any]) -> VerificationResult:
        ticket_id = ((state.get("execution") or {}).get("details") or {}).get("ticket_id")
        res = await services().mcp.call(
            "tickets.get", {"ticket_id": ticket_id or "?"}, agent_id="echo", allowlist=None
        )
        ok = res.ok and not res.text.startswith("ERROR")
        return VerificationResult(
            ok=ok, summary=f"{ticket_id} is in the tracker" if ok else res.text
        )

    def report_extras(self, state: dict[str, Any]) -> dict[str, Any]:
        details = (state.get("execution") or {}).get("details") or {}
        extras = {k: details[k] for k in ("ticket_id", "emailed_to") if details.get(k)}
        if details.get("ticket_id"):
            extras["answer"] = draft_markdown(
                self._draft(state["mission_id"]), details["ticket_id"]
            )
        return extras


def notifier_html(d: TicketDraft, ticket_id: str) -> str:
    from nexus.hitl.result_email import markdown_html

    return (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:640px">'
        + markdown_html(draft_markdown(d, ticket_id))
        + "</div>"
    )
