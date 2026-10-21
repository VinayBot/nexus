"""One error shape for every failure: ``{"detail": ..., "request_id": ...}``.

``detail`` keeps FastAPI's meaning (a message, or the validation error list), so clients
need no changes; ``request_id`` matches the ``X-Request-ID`` header and the server log.
Unexpected exceptions are logged with their traceback and never leak internals.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from nexus.core.logging import get_logger

log = get_logger(__name__)


def _body(request: Request, detail: Any) -> dict[str, Any]:
    return {"detail": detail, "request_id": getattr(request.state, "request_id", None)}


def install(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            _body(request, exc.detail), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        from fastapi.encoders import jsonable_encoder

        return JSONResponse(_body(request, jsonable_encoder(exc.errors())), status_code=422)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception(
            "api.unhandled",
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
        )
        return JSONResponse(
            _body(request, "Something went wrong on the server. Quote the request id."),
            status_code=500,
        )
