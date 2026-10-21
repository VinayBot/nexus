"""Result emails: preferences, SMTP or Sign in with Google, the prompt intent preview,
and a test send. Nothing secret is ever returned."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from nexus.core.logging import get_logger
from nexus.core.services import services

router = APIRouter(tags=["notify"])
log = get_logger(__name__)

#: The only words the Google sign-in redirect can carry back to the UI.
GOOGLE_OUTCOMES = frozenset({"cancelled", "expired", "not_configured", "refused", "failed"})


class NotifyPrefs(BaseModel):
    to: str | None = None
    enabled: bool = True


@router.get("/notify")
async def notify_status() -> dict[str, Any]:
    n = services().notifier
    return {**n.status(), "waiting": len(await n.pending())}


@router.post("/notify/resend")
async def notify_resend() -> dict[str, int]:
    result: dict[str, int] = await services().notifier.resend_pending()
    return result


@router.put("/notify")
async def notify_save(body: NotifyPrefs) -> dict[str, Any]:
    try:
        services().notifier.save(to=(body.to or "").strip() or None, enabled=body.enabled)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return dict(services().notifier.status())


class SmtpAccount(BaseModel):
    provider: Literal["gmail", "outlook"] = "gmail"
    username: str
    app_password: str


@router.put("/notify/smtp")
async def notify_connect(body: SmtpAccount) -> dict[str, Any]:
    try:
        await services().notifier.connect(body.provider, body.username.strip(), body.app_password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return dict(services().notifier.status())


@router.delete("/notify/smtp")
async def notify_disconnect() -> dict[str, Any]:
    services().notifier.disconnect()
    return dict(services().notifier.status())


class GoogleClient(BaseModel):
    client_id: str
    client_secret: str


@router.put("/notify/google/client")
async def google_client(body: GoogleClient) -> dict[str, Any]:
    try:
        services().google_mail.save_client(body.client_id, body.client_secret)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return dict(services().notifier.status())


@router.get("/notify/google/start")
async def google_start() -> dict[str, str]:
    try:
        return {"url": services().google_mail.auth_url()}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/notify/google/callback", include_in_schema=False)
async def google_callback(
    code: str | None = None, state: str | None = None, error: str | None = None
) -> RedirectResponse:
    """Google sends the browser back here; we finish sign-in and return to Settings.

    The redirect target is fixed (our own UI) and carries only a word from
    ``GOOGLE_OUTCOMES``: nothing from the request is echoed into the URL. Details are
    logged, and the account shows up in ``GET /notify``.
    """
    from nexus.hitl.google_mail import GoogleMailError

    settings_page = services().settings.ui_url.rstrip("/") + "/settings"
    if error or not code or not state:
        return RedirectResponse(f"{settings_page}?google_error=cancelled")
    try:
        await services().google_mail.finish(code, state)
    except GoogleMailError as exc:
        log.warning("google.sign_in_failed", reason=str(exc))
        outcome = exc.code if exc.code in GOOGLE_OUTCOMES else "failed"
        return RedirectResponse(f"{settings_page}?google_error={outcome}")
    return RedirectResponse(f"{settings_page}?google=connected")


@router.delete("/notify/google")
async def google_disconnect() -> dict[str, Any]:
    await services().google_mail.disconnect()
    return dict(services().notifier.status())


class IntentRequest(BaseModel):
    task: str = Field(max_length=5000)


@router.post("/notify/intent")
async def notify_intent(body: IntentRequest) -> dict[str, Any]:
    """Live preview for the composer: will this prompt email its result, and to whom?"""
    from nexus.hitl.email_intent import email_request

    req = email_request(body.task)
    n = services().notifier
    to = n.recipients(
        {"email_requested": req.requested, "email_to": req.to, "email_self": req.to_self}
    )
    return {
        "requested": req.requested,
        "to": to,
        "needs_address": req.requested and not to,
        "delivery": n.status()["delivery"],
    }


@router.post("/notify/test")
async def notify_test() -> dict[str, str | None]:
    try:
        return dict(await services().notifier.send_test())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
