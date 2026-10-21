"""The request guard: who is calling, and may they?

Applied to every API router. It reads the session from the HttpOnly cookie (browsers,
including WebSockets and download links) or a Bearer token (API clients), never from the
URL. It refuses cross-site unsafe requests made with the cookie (CSRF), loads the account
so a role change or a deleted account takes effect at once, and checks
``policy.required_role``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from http.cookies import CookieError, SimpleCookie

import jwt
from fastapi import HTTPException, Request

from nexus.auth.policy import required_role
from nexus.auth.security import ROLE_RANK, decode_token
from nexus.core.services import services
from nexus.db.models import RevokedTokenRow, UserRow


@dataclass(frozen=True)
class CurrentUser:
    username: str
    role: str


LOCAL_OWNER = CurrentUser("owner", "owner")  # the identity when auth is switched off


#: The browser session lives in an HttpOnly cookie: page scripts can never read it.
SESSION_COOKIE = "nexus_session"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def bearer_token(headers: Mapping[str, str]) -> str | None:
    """``Authorization: Bearer …``: scripts, the CLI and API clients."""
    header = headers.get("authorization", "")
    return (header[7:].strip() or None) if header.lower().startswith("bearer ") else None


def cookie_token(headers: Mapping[str, str]) -> str | None:
    """The browser's session cookie, if any."""
    jar = SimpleCookie()
    try:
        jar.load(headers.get("cookie", ""))
    except CookieError:
        return None
    morsel = jar.get(SESSION_COOKIE)
    return morsel.value or None if morsel is not None else None


def token_from(headers: Mapping[str, str]) -> str | None:
    """A session token from the header or the cookie (never from the URL, where it leaks)."""
    return bearer_token(headers) or cookie_token(headers)


def cross_site(headers: Mapping[str, str], own_origin: str) -> bool:
    """CSRF / cross-site WebSocket check for cookie sessions: a browser always sends
    ``Origin`` on cross-origin requests, so a foreign one is refused. Requests without
    ``Origin`` are not cross-site browser requests (curl, server-to-server)."""
    origin = headers.get("origin")
    if not origin or bearer_token(headers) or not cookie_token(headers):
        return False
    allowed = {o.rstrip("/") for o in services().settings.cors_origins} | {own_origin}
    return origin.rstrip("/") not in allowed


async def user_for_token(token: str | None) -> CurrentUser | None:
    svc = services()
    if not svc.settings.auth_enabled:
        return LOCAL_OWNER
    if not token:
        return None
    try:
        claims = decode_token(token, svc.settings.secret_key)
    except jwt.InvalidTokenError:
        return None
    async with svc.db.session() as s:
        if await s.get(RevokedTokenRow, str(claims.get("jti", ""))) is not None:
            return None  # signed out
        row = await s.get(UserRow, str(claims.get("sub", "")))
    return CurrentUser(row.username, row.role) if row is not None else None


async def guard(request: Request) -> CurrentUser | None:
    """Router dependency: 401 without a valid session, 403 when the role is too low."""
    need = required_role(request.method, request.url.path)
    own = f"{request.url.scheme}://{request.url.netloc}"
    if request.method in UNSAFE_METHODS and cross_site(request.headers, own):
        raise HTTPException(403, "Cross-site request refused.")
    user = await user_for_token(token_from(request.headers))
    request.state.user = user
    if need is None:
        return user
    if user is None:
        raise HTTPException(401, "Sign in to use NEXUS.", headers={"WWW-Authenticate": "Bearer"})
    if ROLE_RANK[user.role] < ROLE_RANK[need]:
        raise HTTPException(403, f"This needs the {need} role; you are {user.role}.")
    return user
