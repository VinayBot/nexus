"""The request guard: who is calling, and may they?

Applied to every API router. It reads a Bearer token (or ``?token=`` for links and
WebSockets, which cannot send headers), loads the account so a role change or a
deleted account takes effect at once, and checks ``policy.required_role``.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import HTTPException, Request

from nexus.auth.policy import required_role
from nexus.auth.security import ROLE_RANK, decode_token
from nexus.core.services import services
from nexus.db.models import UserRow


@dataclass(frozen=True)
class CurrentUser:
    username: str
    role: str


LOCAL_OWNER = CurrentUser("owner", "owner")  # the identity when auth is switched off


def token_from(request_headers: dict[str, str], query: dict[str, str]) -> str | None:
    header = request_headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return query.get("token") or None


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
        row = await s.get(UserRow, str(claims.get("sub", "")))
    return CurrentUser(row.username, row.role) if row is not None else None


async def guard(request: Request) -> CurrentUser | None:
    """Router dependency: 401 without a valid session, 403 when the role is too low."""
    need = required_role(request.method, request.url.path)
    user = await user_for_token(token_from(dict(request.headers), dict(request.query_params)))
    request.state.user = user
    if need is None:
        return user
    if user is None:
        raise HTTPException(401, "Sign in to use NEXUS.", headers={"WWW-Authenticate": "Bearer"})
    if ROLE_RANK[user.role] < ROLE_RANK[need]:
        raise HTTPException(403, f"This needs the {need} role; you are {user.role}.")
    return user
