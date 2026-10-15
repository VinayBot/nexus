"""Nova guide chat: Server-Sent Events stream of actions, tokens and sources."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from nexus.core.services import services
from nexus.db.models import GuideMessageRow
from nexus.guide.nova import SUGGESTIONS, answer

router = APIRouter(prefix="/guide", tags=["guide"])


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None
    mission_id: str | None = None


@router.get("/suggestions")
async def suggestions() -> list[str]:
    return SUGGESTIONS


@router.post("/chat")
async def chat(body: Ask) -> EventSourceResponse:
    conversation_id = body.conversation_id or uuid.uuid4().hex[:12]

    async def stream() -> AsyncIterator[dict[str, str]]:
        yield {"event": "meta", "data": json.dumps({"conversation_id": conversation_id})}
        async for item in answer(body.question, conversation_id, body.mission_id):
            yield {"event": item["type"], "data": json.dumps(item)}

    return EventSourceResponse(stream())


@router.get("/history/{conversation_id}")
async def history(conversation_id: str) -> list[dict[str, Any]]:
    async with services().db.session() as s:
        rows = (
            await s.execute(
                select(GuideMessageRow)
                .where(GuideMessageRow.conversation_id == conversation_id)
                .order_by(GuideMessageRow.id)
            )
        ).scalars()
        return [
            {"role": r.role, "content": r.content, "actions": r.actions, "ts": r.ts} for r in rows
        ]
