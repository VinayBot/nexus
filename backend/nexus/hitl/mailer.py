"""SMTP mailer (Mailpit in dev). Every message is also kept in the outbox table, so
the UI can show what was sent — or what would have been sent if SMTP is down."""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from email.message import EmailMessage
from typing import Any

import aiosmtplib

from nexus.core.config import Settings
from nexus.core.event_types import EmailSent
from nexus.core.events import emit
from nexus.core.logging import get_logger
from nexus.db.engine import Database
from nexus.db.models import OutboxRow
from nexus.safety.guardrails import redact

log = get_logger(__name__)


def explain_smtp_error(exc: BaseException, host: str) -> str:
    """Turn an SMTP failure into what to do about it."""
    text = str(exc)
    if type(exc).__name__ == "GoogleMailError":  # already written for a person
        return text
    if isinstance(exc, aiosmtplib.SMTPAuthenticationError) or (
        isinstance(exc, aiosmtplib.SMTPServerDisconnected) and "gmail" in host
    ):
        return (
            "Gmail refused the sign-in. Use a 16-letter App Password "
            "(myaccount.google.com/apppasswords), not your normal Google password."
        )
    if isinstance(exc, ConnectionError | OSError | aiosmtplib.SMTPConnectError):
        return f"Could not reach the mail server {host} ({text[:120]})."
    return f"The mail server rejected the message: {text[:200]}"


class Mailer:
    def __init__(
        self,
        db: Database,
        host: str,
        port: int,
        sender: str = "nexus@nexus.local",
        *,
        username: str | None = None,
        password: str | None = None,
        starttls: bool = False,
    ) -> None:
        self.db = db
        self.host = host
        self.port = port
        self.sender = sender
        self.username = username
        self.password = password
        self.starttls = starttls
        self._reachable_until = 0.0
        #: Why the last send failed, in words a person can act on (None after a success).
        self.last_error: str | None = None
        #: Set when the owner signed in with Google: mail then goes through the Gmail API.
        self.google: Any = None

    @classmethod
    def from_settings(cls, db: Database, settings: Settings) -> Mailer:
        """Mailpit in dev; a real provider when SMTP credentials are set in .env."""
        user = settings.smtp_username
        return cls(
            db,
            settings.smtp_host,
            settings.smtp_port,
            # providers such as Gmail only send "From" the signed-in account
            sender=f"NEXUS <{user}>" if user else "nexus@nexus.local",
            username=user,
            password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
            starttls=settings.smtp_starttls,
        )

    @property
    def google_account(self) -> str | None:
        return self.google.account() if self.google is not None else None

    @property
    def real_delivery(self) -> bool:
        return bool(self.google_account or (self.username and self.password))

    async def reachable(self) -> bool:
        """Fast TCP probe (aiosmtplib waits its full timeout even on a refused port)."""
        if time.monotonic() < self._reachable_until:
            return True
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(self.host, self.port), 1.0)
        except (OSError, TimeoutError):
            return False
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
        self._reachable_until = time.monotonic() + 30
        return True

    async def send(
        self,
        to: str,
        subject: str,
        html: str,
        *,
        mission_id: str | None = None,
        text: str | None = None,
    ) -> tuple[str, str]:
        """Returns (message_id, status) where status is 'sent' or 'outbox'."""
        # never leak secrets by email; the owner's own address is allowed through
        html, _ = redact(html, pii=False)
        message_id = f"<{uuid.uuid4().hex}@nexus.local>"
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject
        msg["Message-ID"] = message_id
        msg.set_content(text or "This message needs an HTML-capable mail client.")
        msg.add_alternative(html, subtype="html")
        status = "sent"
        google = self.google_account
        if google:
            msg.replace_header("From", f"NEXUS <{google}>")
        try:
            if google:
                await self.google.send(msg)
            elif not await self.reachable():
                raise ConnectionError(f"SMTP {self.host}:{self.port} unreachable")
            else:
                await aiosmtplib.send(
                    msg,
                    hostname=self.host,
                    port=self.port,
                    timeout=15 if self.real_delivery else 5,
                    username=self.username,
                    password=self.password,
                    start_tls=self.starttls or None,
                )
        except Exception as exc:
            status = "outbox"
            self.last_error = (
                explain_smtp_error(exc, self.host)
                if self.real_delivery or self.host not in {"127.0.0.1", "localhost"}
                else "Not signed in with Google yet. Sign in under Settings → Email results; "
                "this email waits in the outbox and can be sent from there. "
                f"(Local mail server {self.host}:{self.port}: {str(exc)[:80] or type(exc).__name__})"
            )
            log.warning("mail.smtp_unavailable", error=str(exc), to=to)
        else:
            self.last_error = None
        async with self.db.session() as s:
            s.add(
                OutboxRow(
                    id=message_id,
                    to=to,
                    subject=subject,
                    html=html,
                    status=status,
                    mission_id=mission_id,
                )
            )
        emit(
            "email.sent",
            EmailSent(to=to, subject=subject[:200], message_id=message_id, status=status),
            mission_id=mission_id,
        )
        return message_id, status
