"""Email the owner each mission's result (Settings → Email results).

Sent when a mission completes or fails, to the configured address only (the owner's
own inbox; mail to anyone else still needs an approval). The message mirrors the
result card: You asked → outcome → link / download → output → how the team did it.
The address and on/off switch live in ``<data_dir>/notify.json`` so the UI can
change them at runtime; ``NEXUS_RESULT_EMAIL`` seeds the default.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
from typing import Any

from nexus.core.config import Settings
from nexus.core.logging import get_logger
from nexus.db import repo
from nexus.db.engine import Database
from nexus.hitl.email_body import compose_result
from nexus.hitl.mailer import Mailer

log = get_logger(__name__)
FILE = "notify.json"
SMTP_FILE = "smtp.json"  # data/ is gitignored; written owner-read-only
PROVIDERS = {"gmail": ("smtp.gmail.com", 587), "outlook": ("smtp.office365.com", 587)}
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
APP_PASSWORD = re.compile(r"[a-z]{16}")


def parse_recipients(text: str) -> list[str]:
    """Valid addresses from "a@x.com, b@y.org; c@z.io" (duplicates and junk dropped)."""
    out: list[str] = []
    for a in re.split(r"[,;\s]+", text.strip()):
        if EMAIL.match(a) and a.lower() not in {x.lower() for x in out}:
            out.append(a)
    return out[:10]


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

    async def connect(self, provider: str, username: str, password: str) -> None:
        """Check the credentials with the provider first; save them only if they work."""
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}")
        if not EMAIL.match(username):
            raise ValueError(f"not an email address: {username!r}")
        password = password.replace(" ", "")
        if provider == "gmail" and not APP_PASSWORD.fullmatch(password):
            raise ValueError(
                "That is not a Gmail App Password. App Passwords are 16 lowercase letters "
                "(shown as four groups of four). Create one at "
                "myaccount.google.com/apppasswords. Never paste your normal Google password."
            )
        host, port = PROVIDERS[provider]
        await self._login_check(host, port, username, password)
        data = {"provider": provider, "host": host, "port": port, "username": username,
                "password": password}  # fmt: skip
        path = self.settings.data_dir / SMTP_FILE
        path.write_text(json.dumps(data))
        path.chmod(0o600)
        self._apply_smtp(data)

    async def _login_check(self, host: str, port: int, username: str, password: str) -> None:
        import aiosmtplib

        from nexus.hitl.mailer import explain_smtp_error

        smtp = aiosmtplib.SMTP(hostname=host, port=port, timeout=15, start_tls=True)
        try:
            await smtp.connect()
            await smtp.login(username, password)
        except Exception as exc:
            raise ValueError(explain_smtp_error(exc, host)) from exc
        finally:
            with contextlib.suppress(Exception):
                await smtp.quit()

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

    def owner_address(self) -> str | None:
        """Your own inbox: the Google account you signed in with, else the default address."""
        own = parse_recipients(str(self.prefs().get("to") or ""))
        return self.mailer.google_account or (own[0] if own else None)

    def recipients(self, inputs: dict[str, Any] | None) -> list[str]:
        """Who gets this mission's result: only when the prompt (or the composer) asked.

        Addresses named in the request win; "email me" means your own inbox. The
        Settings switch "email every mission" sends to the default address regardless.
        """
        inputs = inputs or {}
        if inputs.get("email_requested"):
            named = inputs.get("email_to") or []
            to = parse_recipients(", ".join(named) if isinstance(named, list) else str(named))
            me = self.owner_address()
            if (inputs.get("email_self") or not to) and me:
                to = [*to, me]
            return parse_recipients(", ".join(to))
        prefs = self.prefs()
        return parse_recipients(str(prefs.get("to") or "")) if prefs.get("enabled") else []

    def save(self, *, to: str | None, enabled: bool) -> dict[str, Any]:
        if to:
            bad = [a for a in re.split(r"[,;\s]+", to.strip()) if a and not EMAIL.match(a)]
            if bad:
                raise ValueError(f"not an email address: {bad[0]!r}")
            to = ", ".join(parse_recipients(to))
        prefs = {"to": to or None, "enabled": enabled}
        (self.settings.data_dir / FILE).write_text(json.dumps(prefs))
        if to:
            self.settings.owner_email = to
        return prefs

    def status(self) -> dict[str, Any]:
        saved = self._saved_smtp() or {}
        google = self.mailer.google
        return {
            **self.prefs(),
            "delivery": "google"
            if self.mailer.google_account
            else ("smtp" if self.mailer.real_delivery else "mailpit"),
            "google_account": self.mailer.google_account,
            "google_ready": bool(google and google.client()),
            "google_redirect": google.redirect_uri if google else None,
            "smtp": f"{self.mailer.host}:{self.mailer.port}",
            "account": self.mailer.username,
            "last_error": self.mailer.last_error,
            "provider": saved.get("provider"),
        }

    # -- sending -------------------------------------------------------------------
    def on_finished(self, mission_id: str) -> None:
        """Runner hook: send in the background so a slow SMTP never delays a mission."""
        task = asyncio.create_task(self.send_result(mission_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def send_result(self, mission_id: str) -> str | None:
        row = await repo.get_mission(self.db, mission_id)
        if row is None or (row.report or {}).get("emailed_to"):
            return None  # the mission already emailed its own result (e.g. a new ticket)
        to = self.recipients(row.inputs)
        if not to:
            return None
        try:
            subject, body, text = self.compose(row)
            status = "sent"
            for address in to:
                _, one = await self.mailer.send(
                    address, subject, body, mission_id=mission_id, text=text
                )
                status = one if one != "sent" else status
            await repo.update_mission(
                self.db,
                mission_id,
                report={
                    **(row.report or {}),
                    "email": {"to": to, "status": status, "error": self.mailer.last_error},
                },
            )
            return status
        except Exception as exc:  # a notification must never break anything
            log.warning("result_email.failed", mission_id=mission_id, error=str(exc))
            return None

    async def pending(self) -> list[Any]:
        """Emails still waiting in the outbox from the last three days."""
        from sqlalchemy import select

        from nexus.db.models import OutboxRow

        async with self.db.session() as s:
            rows = await s.execute(
                select(OutboxRow)
                .where(OutboxRow.status == "outbox", OutboxRow.ts > time.time() - 3 * 86400)
                .order_by(OutboxRow.ts)
            )
            return list(rows.scalars())

    async def resend_pending(self) -> dict[str, int]:
        """After signing in: send everything that waited. Old rows become 'resent'."""
        from nexus.db.models import OutboxRow

        sent = failed = 0
        for row in await self.pending():
            _, status = await self.mailer.send(
                row.to, row.subject, row.html, mission_id=row.mission_id
            )
            async with self.db.session() as s:
                old = await s.get(OutboxRow, row.id)
                if old is not None and status == "sent":
                    old.status = "resent"
            sent, failed = (sent + 1, failed) if status == "sent" else (sent, failed + 1)
            if status != "sent":
                break  # the server is still unreachable: keep the rest waiting
        return {"sent": sent, "failed": failed}

    async def send_test(self) -> dict[str, str | None]:
        to = parse_recipients(str(self.prefs().get("to") or ""))
        if not to:
            raise ValueError("set an address first")
        _, status = await self.mailer.send(
            to[0],
            "[NEXUS] Test email",
            "<p>This is a test from NEXUS. Mission results will arrive like this.</p>",
            text="This is a test from NEXUS. Mission results will arrive like this.",
        )
        return {"status": status, "error": None if status == "sent" else self.mailer.last_error}

    def compose(self, row: Any) -> tuple[str, str, str]:
        return compose_result(row, self.settings)
