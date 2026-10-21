"""X-Request-ID: accept a sane one from the client or proxy, else make one; bind it to
every log line of the request and echo it on the response, so a user's error report
can be matched to the server log."""

from __future__ import annotations

import re
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = b"x-request-id"
_SAFE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        given = dict(scope["headers"]).get(HEADER, b"").decode("latin-1")
        request_id = given if _SAFE.match(given) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != HEADER]
                headers.append((HEADER, request_id.encode()))
                message["headers"] = headers
            await send(message)

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            await self.app(scope, receive, send_with_id)
