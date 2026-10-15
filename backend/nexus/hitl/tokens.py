"""Signed, expiring, single-use approval tokens for email links.

A token encodes (approval id, decision, jti). ``itsdangerous`` signs it with the
server secret and stamps the time, so a tampered or expired link is rejected.
Single use: the jti is inserted into ``used_tokens`` (primary key) when the
decision is applied; a second click finds the jti and is refused.
"""

from __future__ import annotations

import uuid
from typing import Literal

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from nexus.db.engine import Database
from nexus.db.models import UsedTokenRow

Decision = Literal["approve", "reject"]
MAX_AGE_S = 24 * 3600


class TokenError(ValueError):
    pass


class ApprovalToken(BaseModel):
    approval_id: str
    decision: Decision
    jti: str


class TokenService:
    def __init__(self, secret: str, db: Database, max_age_s: int = MAX_AGE_S) -> None:
        self._s = URLSafeTimedSerializer(secret, salt="nexus-approval-v1")
        self.db = db
        self.max_age_s = max_age_s

    def issue(self, approval_id: str, decision: Decision) -> str:
        return self._s.dumps({"aid": approval_id, "d": decision, "jti": uuid.uuid4().hex})

    def verify(self, token: str) -> ApprovalToken:
        try:
            data = self._s.loads(token, max_age=self.max_age_s)
        except SignatureExpired as exc:
            raise TokenError("this approval link has expired") from exc
        except BadSignature as exc:
            raise TokenError("this approval link is invalid") from exc
        return ApprovalToken(approval_id=data["aid"], decision=data["d"], jti=data["jti"])

    async def is_used(self, jti: str) -> bool:
        async with self.db.session() as s:
            return await s.get(UsedTokenRow, jti) is not None

    async def consume(self, token: ApprovalToken) -> None:
        """Mark the token used; raises TokenError if it already was."""
        try:
            async with self.db.session() as s:
                s.add(UsedTokenRow(jti=token.jti))
        except IntegrityError as exc:
            raise TokenError("this approval link was already used") from exc
