"""Security headers on every backend response.

* API and the small HTML pages (email approval confirmations): nothing may load, frame or
  submit anywhere else.
* Published pages (``/sites``): no scripts at all, even if a model slipped one in; framing
  only by the NEXUS app (the result preview).
* ``/docs`` and ``/redoc`` load Swagger UI from a CDN, so they keep the browser default.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

COMMON = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]
API_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'self'; "
    "frame-ancestors 'none'; base-uri 'none'"
)


def site_csp(frame_origins: list[str]) -> str:
    ancestors = " ".join(["'self'", *frame_origins])
    return (
        "script-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; "
        f"frame-ancestors {ancestors}"
    )


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, frame_origins: list[str]) -> None:
        self.app = app
        self.site_policy = site_csp(frame_origins).encode()

    def _extra(self, path: str) -> list[tuple[bytes, bytes]]:
        if path.startswith(("/docs", "/redoc")):
            return []
        if path.startswith("/sites"):
            return [(b"content-security-policy", self.site_policy)]
        return [(b"content-security-policy", API_CSP.encode()), (b"x-frame-options", b"DENY")]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        added = [*COMMON, *self._extra(scope["path"])]

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                names = {k for k, _ in added}
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in names]
                message["headers"] = [*headers, *added]
            await send(message)

        await self.app(scope, receive, send_with_headers)
