"""Password hashing (Argon2id) and signed session tokens (JWT, HS256).

Argon2id is memory-hard, so offline guessing on GPUs is expensive; the hash string
carries its own parameters and salt, and ``needs_rehash`` upgrades old hashes on login.
"""

from __future__ import annotations

import time
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

Role = Literal["owner", "operator", "viewer"]
ROLE_RANK: dict[str, int] = {"viewer": 0, "operator": 1, "owner": 2}
_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored: str, password: str) -> bool:
    try:
        return _hasher.verify(stored, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored: str) -> bool:
    return _hasher.check_needs_rehash(stored)


def create_token(username: str, role: str, secret: str, ttl_s: int) -> str:
    now = int(time.time())
    claims = {"sub": username, "role": role, "iat": now, "exp": now + ttl_s}
    return jwt.encode(claims, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict[str, Any]:
    """Raises ``jwt.InvalidTokenError`` (expired, tampered, malformed)."""
    claims: dict[str, Any] = jwt.decode(token, secret, algorithms=["HS256"])
    return claims
