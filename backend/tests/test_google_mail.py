"""Sign in with Google + Gmail API sending, against a fake Google (no network)."""

from __future__ import annotations

import base64
import json
from email import message_from_bytes
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from nexus.core.config import get_settings
from nexus.core.runtime import runtime
from nexus.hitl import google_mail
from nexus.hitl.google_mail import GoogleMailError
from nexus.llm.scripted import ScriptedLLM

CLIENT_ID = "123-abc.apps.googleusercontent.com"


def _jwt(claims: dict[str, Any]) -> str:
    part = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"x.{part}.y"


class FakeGoogle:
    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self.refresh_ok = True

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(google_mail.TOKEN_URL):
            form = parse_qs(request.content.decode())
            if form["grant_type"] == ["authorization_code"]:
                assert form["code_verifier"][0]  # PKCE
                return httpx.Response(
                    200,
                    json={
                        "access_token": "at-1",
                        "refresh_token": "rt-1",
                        "expires_in": 3600,
                        "id_token": _jwt({"email": "me@gmail.com"}),
                    },
                )
            if not self.refresh_ok:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "at-2", "expires_in": 3600})
        if url.startswith(google_mail.SEND_URL):
            assert request.headers["Authorization"].startswith("Bearer at-")
            raw = json.loads(request.content)["raw"]
            self.sent.append(base64.urlsafe_b64decode(raw))
            return httpx.Response(200, json={"id": "m1"})
        if url.startswith(google_mail.REVOKE_URL):
            return httpx.Response(200)
        return httpx.Response(404)


@pytest.fixture
def fake_google(monkeypatch: pytest.MonkeyPatch) -> FakeGoogle:
    fake = FakeGoogle()
    real = httpx.AsyncClient

    def client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(fake.handler)
        return real(*args, **kwargs)

    monkeypatch.setattr("nexus.hitl.google_mail.httpx.AsyncClient", client)
    monkeypatch.setenv("NEXUS_SMTP_PORT", "9")
    get_settings.cache_clear()
    return fake


async def test_sign_in_with_google_then_send_through_gmail(fake_google: FakeGoogle) -> None:
    async with runtime(get_settings(), provider=ScriptedLLM(), recover=False) as svc:
        g = svc.google_mail
        with pytest.raises(ValueError, match="client ID"):
            g.save_client("not-a-client-id", "secret-value-123")
        with pytest.raises(ValueError, match="one-time setup"):
            g.auth_url()
        g.save_client(CLIENT_ID, "secret-value-123")
        url = urlparse(g.auth_url())
        q = parse_qs(url.query)
        assert q["client_id"] == [CLIENT_ID] and q["code_challenge_method"] == ["S256"]
        assert q["scope"][0].endswith("auth/gmail.send")
        assert q["redirect_uri"][0].startswith("http://127.0.0.1")

        with pytest.raises(GoogleMailError, match="expired"):
            await g.finish("code", "forged-state")
        assert await g.finish("code-1", q["state"][0]) == "me@gmail.com"
        assert (svc.settings.data_dir / "google.json").stat().st_mode & 0o777 == 0o600

        status = svc.notifier.status()
        assert status["delivery"] == "google" and status["google_account"] == "me@gmail.com"
        assert "rt-1" not in json.dumps(status)

        _, sent = await _send(svc)
        assert sent == "sent"
        mail = message_from_bytes(fake_google.sent[-1])
        assert mail["To"] == "anyone@example.com" and "me@gmail.com" in mail["From"]

        fake_google.refresh_ok = False
        g._access = None
        _, status_after = await _send(svc)
        assert status_after == "outbox"
        assert "Sign in with Google again" in (svc.notifier.mailer.last_error or "")

        await g.disconnect()
        assert svc.notifier.status()["delivery"] == "mailpit"


async def _send(svc: Any) -> tuple[str, str]:
    result: tuple[str, str] = await svc.notifier.mailer.send(
        "anyone@example.com", "[NEXUS] hi", "<p>hi</p>", text="hi"
    )
    return result


async def test_waiting_emails_are_sent_after_sign_in(fake_google: FakeGoogle) -> None:
    async with runtime(get_settings(), provider=ScriptedLLM(), recover=False) as svc:
        n = svc.notifier
        _, first = await n.mailer.send("boss@example.com", "[NEXUS] Completed: x", "<p>x</p>")
        assert first == "outbox" and "Not signed in with Google" in (n.mailer.last_error or "")
        assert len(await n.pending()) == 1
        g = svc.google_mail
        g.save_client(CLIENT_ID, "secret-value-123")
        state = parse_qs(urlparse(g.auth_url()).query)["state"][0]
        await g.finish("code-1", state)
        assert await n.resend_pending() == {"sent": 1, "failed": 0}
        assert await n.pending() == []
        assert message_from_bytes(fake_google.sent[-1])["To"] == "boss@example.com"
