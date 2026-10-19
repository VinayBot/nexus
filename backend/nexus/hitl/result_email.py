"""Email the owner each mission's result (Settings → Email results).

Sent when a mission completes or fails, to the configured address only (the owner's
own inbox; mail to anyone else still needs an approval). The message mirrors the
result card: You asked → outcome → link / download → output → how the team did it.
The address and on/off switch live in ``<data_dir>/notify.json`` so the UI can
change them at runtime; ``NEXUS_RESULT_EMAIL`` seeds the default.
"""

from __future__ import annotations

import asyncio
import html
import json
import re
from typing import Any

from nexus.core.config import Settings
from nexus.core.logging import get_logger
from nexus.db import repo
from nexus.db.engine import Database
from nexus.hitl.mailer import Mailer

log = get_logger(__name__)
FILE = "notify.json"
SMTP_FILE = "smtp.json"  # data/ is gitignored; written owner-read-only
PROVIDERS = {"gmail": ("smtp.gmail.com", 587), "outlook": ("smtp.office365.com", 587)}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

OUTCOME = {
    "success": ("Completed", "#16a34a"),
    "partial": ("Partly done", "#d97706"),
    "rejected": ("Rejected by you", "#6b7280"),
    "blocked": ("Blocked by policy", "#dc2626"),
    "rolled_back": ("Rolled back", "#d97706"),
    "failed": ("Stopped with an error", "#dc2626"),
}


def _inline(text: str) -> str:
    out = html.escape(text)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    return re.sub(r"(?<![\w*])_([^_]+)_(?![\w*])", r"<i>\1</i>", out)


def markdown_html(md: str) -> str:
    """Just enough Markdown for an email: headings, bullets, code blocks, paragraphs."""
    parts: list[str] = []
    in_list = in_code = False
    code: list[str] = []
    for line in md.splitlines():
        if line.strip().startswith("```"):
            if in_code:
                parts.append(
                    '<pre style="background:#f4f4f5;padding:10px;border-radius:6px;'
                    'font-size:12px;overflow:auto">' + html.escape("\n".join(code)) + "</pre>"
                )
                code = []
            in_code = not in_code
            continue
        if in_code:
            code.append(line)
            continue
        bullet = re.match(r"^\s*[-*]\s+(.*)", line)
        if in_list and not bullet:
            parts.append("</ul>")
            in_list = False
        if bullet:
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{_inline(bullet.group(1))}</li>")
        elif m := re.match(r"^(#{1,3})\s+(.*)", line):
            size = {1: 20, 2: 16, 3: 15}[len(m.group(1))]
            parts.append(f'<p style="font-size:{size}px;font-weight:600">{_inline(m.group(2))}</p>')
        elif line.strip():
            parts.append(f"<p>{_inline(line)}</p>")
    if in_list:
        parts.append("</ul>")
    return "\n".join(parts)


class ResultNotifier:
    def __init__(self, settings: Settings, mailer: Mailer, db: Database) -> None:
        self.settings = settings
        self.mailer = mailer
        self.db = db
        self._tasks: set[asyncio.Task[str | None]] = set()
        self._apply_smtp(self._saved_smtp())
        if self.prefs().get("to"):  # approval emails go to the same real inbox
            settings.owner_email = str(self.prefs()["to"])

    # -- SMTP account (Settings → Email results → Connect Gmail) ----------------------
    def _saved_smtp(self) -> dict[str, Any] | None:
        try:
            data: dict[str, Any] = json.loads((self.settings.data_dir / SMTP_FILE).read_text())
        except (OSError, ValueError):
            return None
        return data

    def _apply_smtp(self, data: dict[str, Any] | None) -> None:
        m = self.mailer
        if data:
            m.host, m.port = str(data["host"]), int(data["port"])
            m.username, m.password = str(data["username"]), str(data["password"])
            m.starttls, m.sender = True, f"NEXUS <{data['username']}>"
        else:
            st = self.settings
            m.host, m.port, m.starttls = st.smtp_host, st.smtp_port, st.smtp_starttls
            m.username = st.smtp_username
            m.password = st.smtp_password.get_secret_value() if st.smtp_password else None
            m.sender = f"NEXUS <{m.username}>" if m.username else "nexus@nexus.local"
        m._reachable_until = 0.0  # re-probe the new server

    def connect(self, provider: str, username: str, password: str) -> None:
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}")
        if not EMAIL.match(username):
            raise ValueError(f"not an email address: {username!r}")
        password = password.replace(" ", "")
        if len(password) < 8:
            raise ValueError("paste the app password (Gmail: 16 letters)")
        host, port = PROVIDERS[provider]
        data = {"provider": provider, "host": host, "port": port, "username": username,
                "password": password}  # fmt: skip
        path = self.settings.data_dir / SMTP_FILE
        path.write_text(json.dumps(data))
        path.chmod(0o600)
        self._apply_smtp(data)

    def disconnect(self) -> None:
        (self.settings.data_dir / SMTP_FILE).unlink(missing_ok=True)
        self._apply_smtp(None)

    # -- runtime-editable preferences ----------------------------------------------
    def prefs(self) -> dict[str, Any]:
        defaults = {"to": self.settings.result_email, "enabled": self.settings.email_results}
        try:
            saved = json.loads((self.settings.data_dir / FILE).read_text())
        except (OSError, ValueError):
            saved = {}
        return {**defaults, **saved}

    def save(self, *, to: str | None, enabled: bool) -> dict[str, Any]:
        if to and not EMAIL.match(to):
            raise ValueError(f"not an email address: {to!r}")
        prefs = {"to": to or None, "enabled": enabled}
        (self.settings.data_dir / FILE).write_text(json.dumps(prefs))
        if to:
            self.settings.owner_email = to
        return prefs

    def status(self) -> dict[str, Any]:
        saved = self._saved_smtp() or {}
        return {
            **self.prefs(),
            "delivery": "smtp" if self.mailer.real_delivery else "mailpit",
            "smtp": f"{self.mailer.host}:{self.mailer.port}",
            "account": self.mailer.username,
            "provider": saved.get("provider"),
        }

    # -- sending -------------------------------------------------------------------
    def on_finished(self, mission_id: str) -> None:
        """Runner hook: send in the background so a slow SMTP never delays a mission."""
        task = asyncio.create_task(self.send_result(mission_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def send_result(self, mission_id: str) -> str | None:
        prefs = self.prefs()
        if not (prefs.get("enabled") and prefs.get("to")):
            return None
        row = await repo.get_mission(self.db, mission_id)
        if row is None:
            return None
        try:
            subject, body, text = self.compose(row)
            _, status = await self.mailer.send(
                str(prefs["to"]), subject, body, mission_id=mission_id, text=text
            )
            return status
        except Exception as exc:  # a notification must never break anything
            log.warning("result_email.failed", mission_id=mission_id, error=str(exc))
            return None

    async def send_test(self) -> str:
        to = self.prefs().get("to")
        if not to:
            raise ValueError("set an address first")
        _, status = await self.mailer.send(
            str(to),
            "[NEXUS] Test email",
            "<p>This is a test from NEXUS. Mission results will arrive like this.</p>",
            text="This is a test from NEXUS. Mission results will arrive like this.",
        )
        return status

    def compose(self, row: Any) -> tuple[str, str, str]:
        report: dict[str, Any] = row.report or {}
        key = "failed" if row.status == "failed" else (row.outcome or "partial")
        label, colour = OUTCOME.get(key, (key, "#6b7280"))
        ui = self.settings.ui_url.rstrip("/")
        api = self.settings.public_url.rstrip("/")
        links = []
        if report.get("preview_url"):
            links.append(
                f'<a href="{html.escape(report["preview_url"])}">Open the published page</a>'
            )
        if report.get("download"):
            links.append(
                f'<a href="{api}{html.escape(report["download"])}">Download the project (.zip)</a>'
            )
        links.append(f'<a href="{ui}/missions?m={row.id}">Open the mission in NEXUS</a>')
        if row.status == "failed":
            output = f"<p>{html.escape(row.error or 'Unknown error')[:1500]}</p>"
        else:
            output = markdown_html(str(report.get("answer") or report.get("summary") or ""))
        steps = "".join(
            f"<li>{_inline(h)}</li>" for h in dict.fromkeys(report.get("highlights") or [])
        )
        body = f"""<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:640px;color:#18181b">
<p style="color:#71717a;font-size:12px;margin:0">You asked</p>
<p style="font-size:15px;margin:4px 0 16px">&ldquo;{html.escape(row.task)}&rdquo;</p>
<p><span style="background:{colour};color:#fff;border-radius:999px;padding:3px 10px;font-size:12px;font-weight:600">{label}</span>
&nbsp;{html.escape(str(report.get("summary") or ""))}</p>
<p>{" &middot; ".join(links)}</p>
<hr style="border:none;border-top:1px solid #e4e4e7">
<p style="color:#71717a;font-size:12px">Output</p>
{output}
{f'<hr style="border:none;border-top:1px solid #e4e4e7"><p style="color:#71717a;font-size:12px">How the team did it</p><ol style="font-size:13px;color:#3f3f46">{steps}</ol>' if steps else ""}
<p style="color:#a1a1aa;font-size:11px">Sent by NEXUS on your Mac &middot; {int(report.get("tokens") or row.tokens or 0):,} tokens</p>
</div>"""
        text = f"You asked: {row.task}\n\n{label}\n\n{report.get('answer') or row.error or ''}"
        return f"[NEXUS] {label}: {row.title[:90]}", body, text
