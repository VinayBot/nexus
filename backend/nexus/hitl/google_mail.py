"""Sign in with Google, then send results through the Gmail API as the signed-in user.

No password ever reaches NEXUS: the owner signs in on Google's own page and grants
exactly one permission, ``gmail.send`` (send mail as you; it cannot read the inbox).
Google returns a refresh token, stored in ``<data_dir>/google.json`` (0600, the data
folder is gitignored), and each send trades it for a short-lived access token.

Google requires every app that sends Gmail to be registered once: a free "Desktop
app" OAuth client in Google Cloud. Its client id and secret come from the env
(``NEXUS_GOOGLE_CLIENT_ID`` / ``NEXUS_GOOGLE_CLIENT_SECRET``) or are pasted in
Settings (``google_client.json``). Desktop clients accept the loopback redirect
``http://127.0.0.1:<port>/…`` without registering it, and PKCE protects the code.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlencode

import httpx

from nexus.core.config import Settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
SCOPES = "openid email https://www.googleapis.com/auth/gmail.send"
ACCOUNT_FILE = "google.json"
CLIENT_FILE = "google_client.json"


class GoogleMailError(RuntimeError):
    """``code`` is a fixed word the sign-in redirect may carry; the message stays server-side."""

    def __init__(self, message: str, code: str = "failed") -> None:
        super().__init__(message)
        self.code = code


def _write_private(path: Any, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data))
    path.chmod(0o600)


def _email_from_id_token(id_token: str) -> str:
    """The id token comes straight from Google's token endpoint over TLS: read its claims."""
    payload = id_token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    return str(claims.get("email") or "")


class GoogleMail:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pending: dict[str, tuple[str, float]] = {}  # state -> (pkce verifier, time)
        self._access: tuple[str, float] | None = None

    # -- configuration ------------------------------------------------------------------
    def client(self) -> tuple[str, str] | None:
        st = self.settings
        if st.google_client_id and st.google_client_secret:
            return st.google_client_id, st.google_client_secret.get_secret_value()
        try:
            d = json.loads((st.data_dir / CLIENT_FILE).read_text())
            return str(d["client_id"]), str(d["client_secret"])
        except (OSError, ValueError, KeyError):
            return None

    def save_client(self, client_id: str, client_secret: str) -> None:
        client_id, client_secret = client_id.strip(), client_secret.strip()
        if not client_id.endswith(".apps.googleusercontent.com"):
            raise ValueError("A Google client ID ends with .apps.googleusercontent.com")
        if len(client_secret) < 10:
            raise ValueError("Paste the client secret shown next to the client ID")
        _write_private(
            self.settings.data_dir / CLIENT_FILE,
            {"client_id": client_id, "client_secret": client_secret},
        )

    @property
    def redirect_uri(self) -> str:
        return f"{self.settings.public_url.rstrip('/')}/api/v1/notify/google/callback"

    def account(self) -> str | None:
        try:
            return str(json.loads((self.settings.data_dir / ACCOUNT_FILE).read_text())["email"])
        except (OSError, ValueError, KeyError):
            return None

    # -- sign-in ------------------------------------------------------------------------
    def auth_url(self) -> str:
        client = self.client()
        if client is None:
            raise ValueError("Add the Google client ID and secret first (one-time setup).")
        state = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        now = time.time()
        self._pending = {s: v for s, v in self._pending.items() if now - v[1] < 600}
        self._pending[state] = (verifier, now)
        params = {
            "client_id": client[0],
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    async def finish(self, code: str, state: str) -> str:
        pending = self._pending.pop(state, None)
        client = self.client()
        if pending is None or time.time() - pending[1] > 600:
            raise GoogleMailError(
                "This sign-in link expired. Start again from Settings.", "expired"
            )
        if client is None:
            raise GoogleMailError("The Google client is not configured.", "not_configured")
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client[0],
                    "client_secret": client[1],
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": pending[0],
                },
            )
        body = r.json()
        if r.status_code != 200 or "refresh_token" not in body:
            raise GoogleMailError(
                f"Google refused the sign-in: {body.get('error_description') or body.get('error') or r.status_code}",
                "refused",
            )
        email = _email_from_id_token(body.get("id_token", ""))
        _write_private(
            self.settings.data_dir / ACCOUNT_FILE,
            {"email": email, "refresh_token": body["refresh_token"]},
        )
        self._access = (body["access_token"], time.time() + int(body.get("expires_in", 3000)) - 60)
        return email

    async def disconnect(self) -> None:
        path = self.settings.data_dir / ACCOUNT_FILE
        try:
            token = json.loads(path.read_text())["refresh_token"]
            async with httpx.AsyncClient(timeout=10) as http:
                await http.post(REVOKE_URL, data={"token": token})  # best effort
        except (OSError, ValueError, KeyError, httpx.HTTPError):
            pass  # no token file, a bad file, or Google unreachable: delete locally anyway
        path.unlink(missing_ok=True)
        self._access = None

    # -- sending ------------------------------------------------------------------------
    async def _token(self) -> str:
        if self._access and time.time() < self._access[1]:
            return self._access[0]
        client = self.client()
        try:
            refresh = json.loads((self.settings.data_dir / ACCOUNT_FILE).read_text())[
                "refresh_token"
            ]
        except (OSError, ValueError, KeyError) as exc:
            raise GoogleMailError("Not signed in with Google.") from exc
        if client is None:
            raise GoogleMailError("The Google client is not configured.")
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.post(
                TOKEN_URL,
                data={
                    "client_id": client[0],
                    "client_secret": client[1],
                    "refresh_token": refresh,
                    "grant_type": "refresh_token",
                },
            )
        body = r.json()
        if r.status_code != 200:
            raise GoogleMailError(
                "Google sign-in expired or was revoked. Sign in with Google again in Settings."
                if body.get("error") == "invalid_grant"
                else f"Google token error: {body.get('error_description') or body.get('error')}"
            )
        self._access = (body["access_token"], time.time() + int(body.get("expires_in", 3000)) - 60)
        return self._access[0]

    async def send(self, msg: EmailMessage) -> None:
        token = await self._token()
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        async with httpx.AsyncClient(timeout=20) as http:
            r = await http.post(
                SEND_URL, json={"raw": raw}, headers={"Authorization": f"Bearer {token}"}
            )
        if r.status_code >= 300:
            detail = (
                r.json().get("error", {}).get("message", r.text[:200])
                if r.content
                else r.status_code
            )
            raise GoogleMailError(f"Gmail did not send the message: {detail}")
