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


async def verify(token: str | None, ip: str | None = None, *, post=_post) -> None:
    """Raise ValidationFailedError unless the Turnstile token is valid.

    Skipped (with a warning in production) when TURNSTILE_SECRET isn't configured yet.
    """
    settings = get_settings()
    if not settings.turnstile_secret:
        if settings.is_production:
            log.warning("TURNSTILE_SECRET is not set — CAPTCHA check skipped")
        return
    if not token:
        raise ValidationFailedError("Please complete the security check.")
    try:
        result = await asyncio.to_thread(post, settings.turnstile_secret, token, ip)
    except OSError:
        log.exception("Turnstile verification request failed")
        raise ValidationFailedError("We couldn't verify the security check. Please try again.")
    if not result.get("success"):
        log.info("Turnstile rejected token: %s", result.get("error-codes"))
        raise ValidationFailedError("The security check failed. Please try again.")
