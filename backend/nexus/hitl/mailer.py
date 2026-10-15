"""SMTP mailer (Mailpit in dev). Every message is also kept in the outbox table, so
the UI can show what was sent — or what would have been sent if SMTP is down."""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from email.message import EmailMessage

import aiosmtplib

from nexus.core.event_types import EmailSent
from nexus.core.events import emit
from nexus.core.logging import get_logger
from nexus.db.engine import Database
from nexus.db.models import OutboxRow
from nexus.safety.guardrails import redact

log = get_logger(__name__)


class Mailer:
    def __init__(
        self, db: Database, host: str, port: int, sender: str = "nexus@dojo.local"
    ) -> None:
        self.db = db
        self.host = host
        self.port = port
        self.sender = sender
        self._reachable_until = 0.0

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
        try:
            if not await self.reachable():
                raise ConnectionError(f"SMTP {self.host}:{self.port} unreachable")
            await aiosmtplib.send(msg, hostname=self.host, port=self.port, timeout=5)
        except Exception as exc:
            status = "outbox"
            log.warning("mail.smtp_unavailable", error=str(exc), to=to)
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
