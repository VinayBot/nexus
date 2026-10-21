"""Accounts: first-run setup, login, the current user, and user management (owner).

The first visit creates the owner account (only while no account exists). Login is
rate limited per username + client address against password guessing. Owners add
operators and viewers; the last owner can never be removed or demoted.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from nexus.auth.ratelimit import RateLimiter
from nexus.auth.security import create_token, hash_password, needs_rehash, verify_password
from nexus.core.services import services
from nexus.db import repo
from nexus.db.models import UserRow

router = APIRouter(prefix="/auth", tags=["auth"])
login_limiter = RateLimiter(limit=5, window_s=60)

USERNAME = r"^[a-zA-Z0-9_.-]{3,32}$"


class Credentials(BaseModel):
    username: str = Field(pattern=USERNAME)
    password: str = Field(min_length=8, max_length=128)


class NewUser(Credentials):
    role: str = Field(pattern="^(owner|operator|viewer)$")


class RoleChange(BaseModel):
    role: str = Field(pattern="^(owner|operator|viewer)$")


class Session(BaseModel):
    token: str
    username: str
    role: str


def _session(username: str, role: str) -> Session:
    st = services().settings
    token = create_token(username, role, st.secret_key, st.token_ttl_hours * 3600)
    return Session(token=token, username=username, role=role)


async def _count(role: str | None = None) -> int:
    async with services().db.session() as s:
        q = select(func.count()).select_from(UserRow)
        if role:
            q = q.where(UserRow.role == role)
        return int(await s.scalar(q) or 0)


@router.get("/status")
async def status() -> dict[str, bool]:
    enabled = services().settings.auth_enabled
    return {"auth_enabled": enabled, "setup_required": enabled and await _count() == 0}


@router.post("/setup", response_model=Session, status_code=201)
async def setup(body: Credentials) -> Session:
    """Create the first owner. Refused once any account exists."""
    if await _count() > 0:
        raise HTTPException(409, "NEXUS is already set up; sign in instead.")
    async with services().db.session() as s:
        s.add(
            UserRow(
                username=body.username, password_hash=hash_password(body.password), role="owner"
            )
        )
    await repo.audit(
        services().db, actor=body.username, channel="ui", action="auth.setup", detail={}
    )
    return _session(body.username, "owner")


@router.post("/login", response_model=Session)
async def login(body: Credentials, request: Request) -> Session:
    client = request.client.host if request.client else "?"
    key = f"{body.username.lower()}|{client}"
    if not login_limiter.allow(key):
        raise HTTPException(
            429,
            "Too many sign-in attempts. Wait a minute and try again.",
            headers={"Retry-After": str(login_limiter.retry_after(key))},
        )
    async with services().db.session() as s:
        row = await s.get(UserRow, body.username)
        ok = row is not None and verify_password(row.password_hash, body.password)
        if ok and row is not None and needs_rehash(row.password_hash):
            row.password_hash = hash_password(body.password)  # upgrade old parameters
    if not ok or row is None:
        raise HTTPException(401, "Wrong username or password.")
    return _session(row.username, row.role)


@router.get("/me")
async def me(request: Request) -> dict[str, str | bool]:
    user = request.state.user
    if user is None:
        raise HTTPException(401, "Not signed in.")
    return {
        "username": user.username,
        "role": user.role,
        "auth_enabled": services().settings.auth_enabled,
    }


@router.get("/users")
async def list_users() -> list[dict[str, object]]:
    async with services().db.session() as s:
        rows = (await s.execute(select(UserRow).order_by(UserRow.created_at))).scalars().all()
    return [{"username": r.username, "role": r.role, "created_at": r.created_at} for r in rows]


@router.post("/users", status_code=201)
async def create_user(body: NewUser, request: Request) -> dict[str, str]:
    async with services().db.session() as s:
        if await s.get(UserRow, body.username) is not None:
            raise HTTPException(409, f"User {body.username} already exists.")
        s.add(
            UserRow(
                username=body.username, password_hash=hash_password(body.password), role=body.role
            )
        )
    await repo.audit(
        services().db,
        actor=request.state.user.username,
        channel="ui",
        action="auth.user_created",
        detail={"username": body.username, "role": body.role},
    )
    return {"username": body.username, "role": body.role}


@router.put("/users/{username}")
async def change_role(username: str, body: RoleChange, request: Request) -> dict[str, str]:
    async with services().db.session() as s:
        row = await s.get(UserRow, username)
        if row is None:
            raise HTTPException(404, "No such user.")
        if row.role == "owner" and body.role != "owner" and await _count("owner") <= 1:
            raise HTTPException(409, "NEXUS needs at least one owner.")
        row.role = body.role
    await repo.audit(
        services().db,
        actor=request.state.user.username,
        channel="ui",
        action="auth.role_changed",
        detail={"username": username, "role": body.role},
    )
    return {"username": username, "role": body.role}


@router.delete("/users/{username}", status_code=204)
async def delete_user(username: str, request: Request) -> None:
    if username == request.state.user.username:
        raise HTTPException(409, "You cannot delete your own account.")
    async with services().db.session() as s:
        row = await s.get(UserRow, username)
        if row is None:
            raise HTTPException(404, "No such user.")
        if row.role == "owner" and await _count("owner") <= 1:
            raise HTTPException(409, "NEXUS needs at least one owner.")
        await s.delete(row)
    await repo.audit(
        services().db,
        actor=request.state.user.username,
        channel="ui",
        action="auth.user_deleted",
        detail={"username": username},
    )
