"""Human-feedback memory: what the owner approved or rejected before.

Fed to the Risk Scorer (and shown to the Shogun) so the system learns which
kinds of action its owner trusts.
"""

from __future__ import annotations

from sqlalchemy import func, select

from nexus.core.services import services
from nexus.db.models import ApprovalRow


async def approval_history(action_kind: str) -> dict[str, int]:
    db = services().extras.get("db")
    if db is None:
        return {}
    async with db.session() as s:
        res = await s.execute(
            select(ApprovalRow.status, func.count())
            .where(ApprovalRow.kind == "approve_action")
            .where(func.json_extract(ApprovalRow.payload, "$.action.kind") == action_kind)
            .group_by(ApprovalRow.status)
        )
        counts: dict[str, int] = dict(res.all())
    return {
        "approved": int(counts.get("approved", 0)) + int(counts.get("edited", 0)),
        "rejected": int(counts.get("rejected", 0)),
    }
