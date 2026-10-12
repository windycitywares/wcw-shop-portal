"""Cloudflare Turnstile verification (https://developers.cloudflare.com/turnstile/)."""

import asyncio
import json
import logging
import urllib.parse
import urllib.request

from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError

log = logging.getLogger("wcw.captcha")
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _post(secret: str, token: str, ip: str | None) -> dict:
    data = {"secret": secret, "response": token}
    if ip:
        data["remoteip"] = ip
    req = urllib.request.Request(VERIFY_URL, data=urllib.parse.urlencode(data).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 — fixed https URL
        return json.loads(resp.read())


async def verify(token: str | None, ip: str | None = None, *, action: str, post=_post) -> None:
    """Raise ValidationFailedError unless the Turnstile token is valid, was issued for this `action`
    (the form it was solved on) and, in production, for one of our hostnames.

    Skipped (with a warning in production) when TURNSTILE_SECRET isn't configured yet.
    """
    settings = get_settings()
    if not settings.turnstile_secret:
        if settings.is_production:
            log.warning("TURNSTILE_SECRET is not set — CAPTCHA check skipped")
        return
    if not token or len(token) > 2048:
        raise ValidationFailedError("Please complete the security check.")
    try:
        result = await asyncio.to_thread(post, settings.turnstile_secret, token, ip)
    except OSError:
        log.exception("Turnstile verification request failed")
        raise ValidationFailedError("We couldn't verify the security check. Please try again.")
    if not result.get("success"):
        codes = result.get("error-codes") or []
        if "invalid-input-secret" in codes:
            log.error("Turnstile says TURNSTILE_SECRET is invalid — check backend/.env")
        else:
            log.info("Turnstile rejected token: %s", codes)
        raise ValidationFailedError("The security check failed. Please try again.")
    if result.get("action") != action:
        log.warning("Turnstile action mismatch: expected %s, got %s", action, result.get("action"))
        raise ValidationFailedError("The security check failed. Please try again.")
    allowed = settings.turnstile_hostnames
    if allowed and result.get("hostname") not in allowed:
        log.warning("Turnstile hostname not allowed: %s", result.get("hostname"))
        raise ValidationFailedError("The security check failed. Please try again.")
