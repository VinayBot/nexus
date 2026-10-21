"""WebSocket event streams.

``/ws/missions/{id}?after_seq=N`` first replays persisted events with seq > N, then
streams live ones — so a reconnecting client resumes exactly where it left off.
``/ws/global`` streams mission lifecycle, approvals, governor metrics and health.
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from nexus.auth.guard import cross_site, token_from, user_for_token
from nexus.core.events import bus
from nexus.core.services import services
from nexus.db import repo

router = APIRouter()


async def _pump(ws: WebSocket, mission_id: str | None, after_seq: int) -> None:
    async with bus.subscribe(mission_id) as sub:
        last = after_seq
        if mission_id:
            # Events are broadcast at once but written in batches. Anything emitted before
            # this subscription and not yet written would be in neither the backlog nor the
            # live queue (a new mission's first events went missing): write it now.
            await bus.flush()
            backlog = await repo.events_after(services().db, mission_id, after_seq)
            for ev in backlog:
                await ws.send_json(ev)
                last = max(last, ev["seq"])
        while True:
            event = await sub.queue.get()
            if mission_id and event.seq <= last:
                continue  # already sent from the backlog
            await ws.send_json(event.model_dump(mode="json"))
            if mission_id:
                last = event.seq
            if sub.dropped:
                await ws.send_json({"type": "stream.gap", "dropped": sub.dropped, "seq": last})
                sub.dropped = 0


async def _serve(ws: WebSocket, mission_id: str | None) -> None:
    # the browser sends the session cookie with the handshake; refuse foreign pages
    # (cross-site WebSocket hijacking) and anyone without a session
    scheme = "https" if ws.url.scheme == "wss" else "http"
    if cross_site(ws.headers, f"{scheme}://{ws.url.netloc}"):
        await ws.close(code=4403, reason="cross-site connection refused")
        return
    user = await user_for_token(token_from(ws.headers))
    if user is None:
        await ws.close(code=4401, reason="sign in required")
        return
    await ws.accept()
    after = int(ws.query_params.get("after_seq", "0") or 0)
    pump = asyncio.create_task(_pump(ws, mission_id, after))
    try:
        while True:  # keep reading so we notice disconnects; clients may send pings
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        pump.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await pump


@router.websocket("/ws/missions/{mission_id}")
async def mission_stream(ws: WebSocket, mission_id: str) -> None:
    await _serve(ws, mission_id)


@router.websocket("/ws/global")
async def global_stream(ws: WebSocket) -> None:
    await _serve(ws, None)
