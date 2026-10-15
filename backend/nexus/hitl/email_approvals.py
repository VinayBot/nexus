"""Approval-by-email: render and send the request, and serve the confirm pages.

Flow: approval recorded → Swift emails the owner (Mailpit in dev) with signed
Approve / Reject links → GET shows a confirmation page (safe for link scanners)
→ POST verifies the token, burns it, and resumes the graph via the approval
service exactly as a UI decision would (channel = "email").
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from nexus.core.config import Settings
from nexus.core.event_types import AgentStatus
from nexus.core.events import emit
from nexus.db.models import ApprovalRow
from nexus.graph.schemas import ApprovalDecision
from nexus.hitl.approvals import ApprovalService
from nexus.hitl.mailer import Mailer
from nexus.hitl.tokens import TokenError, TokenService

TEMPLATES = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html"]),
)
RISK_COLORS = {"LOW": "#3fd18b", "MEDIUM": "#ffb020", "HIGH": "#f2662a", "CRITICAL": "#ff4d4f"}
EMAIL_KINDS = {"approve_action", "approve_team"}


class EmailApprovals:
    def __init__(
        self, settings: Settings, approvals: ApprovalService, mailer: Mailer, tokens: TokenService
    ) -> None:
        self.settings = settings
        self.approvals = approvals
        self.mailer = mailer
        self.tokens = tokens
        approvals.on_new.append(self.send_request)

    def _link(self, approval_id: str, decision: str) -> str:
        token = self.tokens.issue(approval_id, decision)  # type: ignore[arg-type]
        return f"{self.settings.public_url}/api/v1/approvals/email/{token}"

    async def send_request(self, row: ApprovalRow) -> None:
        if row.kind not in EMAIL_KINDS:
            return
        p: dict[str, Any] = row.payload
        risk = p.get("risk") or {}
        evidence = [
            {"title": e["title"], "content": str(e["content"])[:1800]}
            for e in (p.get("evidence") or [])
            if e.get("kind") in {"diff", "test_report", "answer", "log"}
        ][:4]
        if p.get("kind") == "approve_team":
            team = ", ".join(m["agent_id"] for m in (p.get("team") or {}).get("members", []))
            steps = "\n".join(
                f"- {s['title']} ({s['role']})" for s in (p.get("plan") or {}).get("steps", [])
            )
            evidence = [{"title": f"Proposed team: {team}", "content": steps}]
        body = TEMPLATES.get_template("approval_email.html").render(
            title=p.get("summary", "Action")[:120],
            mission_id=row.mission_id,
            summary=p.get("summary", ""),
            risk_level=risk.get("level", "—"),
            risk_score=risk.get("score"),
            risk_explanation=risk.get("explanation", ""),
            risk_color=RISK_COLORS.get(risk.get("level", ""), "#c9b2a3"),
            requires_override=bool(p.get("requires_override")),
            verdict=p.get("verdict"),
            evidence=evidence,
            dry_run=p.get("dry_run"),
            approve_url=self._link(row.id, "approve"),
            reject_url=self._link(row.id, "reject"),
            open_url=f"{self.settings.ui_url}/approvals?focus={row.id}",
        )
        emit(
            "agent.status",
            AgentStatus(agent_id="swift", status="running"),
            mission_id=row.mission_id,
            agent_id="swift",
        )
        _, status = await self.mailer.send(
            self.settings.owner_email,
            f"[NEXUS] Approval needed ({risk.get('level', 'team')}): {p.get('summary', '')[:80]}",
            body,
            mission_id=row.mission_id,
            text=f"Approval needed: {p.get('summary', '')}\nOpen: {self.settings.ui_url}/approvals",
        )
        async with self.approvals.db.session() as s:
            fresh = await s.get(ApprovalRow, row.id)
            if fresh is not None:
                fresh.email_status = status
        emit(
            "agent.status",
            AgentStatus(agent_id="swift", status="idle"),
            mission_id=row.mission_id,
            agent_id="swift",
        )

    # -- confirm pages ------------------------------------------------------------------
    async def confirm_page(self, token: str) -> tuple[int, str]:
        try:
            t = self.tokens.verify(token)
        except TokenError as exc:
            return 400, page("Link not valid", str(exc))
        row = await self.approvals.get(t.approval_id)
        if row is None:
            return 404, page("Unknown approval", "This approval no longer exists.")
        if row.status != "pending" or await self.tokens.is_used(t.jti):
            return 409, page(
                "Already decided", f"This request is already <b>{html.escape(row.status)}</b>."
            )
        verb = "Approve" if t.decision == "approve" else "Reject"
        color = "#3fd18b" if t.decision == "approve" else "#8e1b17"
        form = f"""
          <p>{html.escape(str(row.payload.get("summary", "")))}</p>
          <form method="post">
            {'<label>Reason (optional)<br><input name="reason" style="width:100%;padding:8px;border-radius:6px;border:1px solid #6b4a24;background:#0e1116;color:#eee"></label><br><br>' if t.decision == "reject" else ""}
            <button type="submit" style="padding:12px 24px;border:0;border-radius:8px;background:{color};color:#fff;font-weight:bold;font-size:15px;cursor:pointer">Confirm: {verb}</button>
          </form>"""
        return 200, page(f"{verb} this action?", form)

    async def decide(self, token: str, reason: str = "") -> tuple[int, str]:
        try:
            t = self.tokens.verify(token)
            await self.tokens.consume(t)
        except TokenError as exc:
            return 400, page("Link not valid", str(exc))
        decision = ApprovalDecision(
            decision=t.decision,
            by=self.settings.owner_email,
            channel="email",
            reason=reason or f"{t.decision}d by email",
        )
        try:
            await self.approvals.decide(t.approval_id, decision)
        except Exception as exc:
            return 409, page("Could not apply", html.escape(str(exc)))
        done = (
            "approved — the mission is resuming"
            if t.decision == "approve"
            else "rejected — nothing will be changed"
        )
        return 200, page(
            "Done",
            f"The action was <b>{done}</b>.<br><br><a style='color:#f7a440' href='{self.settings.ui_url}/approvals'>Open NEXUS</a>",
        )


def page(title: str, body: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXUS · {html.escape(title)}</title></head>
<body style="margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 50% 70%,#c8341f 0%,#3b0a0a 55%,#140909 100%);font-family:-apple-system,Segoe UI,Helvetica,sans-serif;color:#f6ebe0">
<div style="max-width:480px;margin:24px;padding:28px;background:rgba(30,15,14,.88);border:1px solid #6b4a24;border-radius:16px">
<div style="font-size:12px;letter-spacing:3px;color:#f7a440">NEXUS · APPROVAL REQUIRED</div>
<h1 style="font-family:Georgia,serif;color:#ffd08a;font-size:24px">{html.escape(title)}</h1>{body}</div></body></html>"""
