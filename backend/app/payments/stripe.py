"""Stripe over plain HTTPS (standard library only, no SDK).

We use hosted Checkout: the customer pays on Stripe's page, so card numbers never touch this server.
Stripe then tells us about the payment by webhook, signed with a secret only Stripe and we know.

    create_checkout_session()  -> a URL to send the customer to
    verify_signature()         -> is this webhook really from Stripe?
    refund()                   -> give money back
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

log = logging.getLogger("wcw.stripe")
API = "https://api.stripe.com/v1"
TOLERANCE_SECONDS = 300


def to_cents(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))


def encode_form(data: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """Stripe's form encoding: nested dicts and lists become a[b][0][c]=value."""
    out: list[tuple[str, str]] = []
    for key, value in data.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            out += encode_form(value, name)
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    out += encode_form(item, f"{name}[{i}]")
                else:
                    out.append((f"{name}[{i}]", str(item)))
        elif isinstance(value, bool):
            out.append((name, "true" if value else "false"))
        elif value is not None:
            out.append((name, str(value)))
    return out


def verify_signature(payload: bytes, header: str | None, secret: str, *, now: float | None = None,
                     tolerance: int = TOLERANCE_SECONDS) -> bool:
    """Check a webhook's `Stripe-Signature` header: HMAC-SHA256 over "<timestamp>.<body>"."""
    if not header or not secret:
        return False
    timestamp: str | None = None
    signatures: list[str] = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if not timestamp or not signatures:
        return False
    try:
        age = abs((now if now is not None else time.time()) - int(timestamp))
    except ValueError:
        return False
    if age > tolerance:
        return False
    signed = timestamp.encode() + b"." + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in signatures)


def sign(payload: bytes, secret: str, timestamp: int) -> str:
    """Builds a valid header (used by the tests to play Stripe)."""
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def _request(method: str, path: str, form: list[tuple[str, str]], secret: str, idempotency_key: str | None) -> dict:
    body = urllib.parse.urlencode(form).encode() if form else None
    req = urllib.request.Request(f"{API}{path}", data=body, method=method)
    token = base64.b64encode(f"{secret}:".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if idempotency_key:
        req.add_header("Idempotency-Key", idempotency_key)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 — fixed https URL
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read()).get("error", {}).get("message", "")
        except (ValueError, OSError):
            pass
        raise StripeError(detail or f"Stripe answered {exc.code}", exc.code) from exc


class StripeError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def configured() -> bool:
    from app.core.config import get_settings

    s = get_settings()
    return bool(s.stripe_secret_key and s.stripe_webhook_secret)


async def _call(method: str, path: str, form: list[tuple[str, str]], idempotency_key: str | None = None) -> dict:
    from app.core.config import get_settings
    from app.core.exceptions import ServiceUnavailableError

    secret = get_settings().stripe_secret_key
    if not secret:
        raise ServiceUnavailableError("Card payments aren't set up yet.")
    try:
        return await asyncio.to_thread(_request, method, path, form, secret, idempotency_key)  # looked up now, so tests can swap it
    except (StripeError, OSError) as exc:
        log.error("Stripe call %s %s failed: %s", method, path, exc)
        raise


def checkout_form(*, order_number: str, email: str, amount: Decimal, currency: str, description: str,
                  success_url: str, cancel_url: str) -> list[tuple[str, str]]:
    return encode_form({
        "mode": "payment",
        "client_reference_id": order_number,
        "customer_email": email,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items": [{
            "quantity": 1,
            "price_data": {
                "currency": currency.lower(),
                "unit_amount": to_cents(amount),
                "product_data": {"name": f"WindyCityWares order {order_number}", "description": description[:300]},
            },
        }],
        "metadata": {"order_number": order_number},
        "payment_intent_data": {"metadata": {"order_number": order_number}},
        # Stripe closes an unpaid session after 30 minutes; the order is released a little later.
        "expires_at": int(time.time()) + 31 * 60,
    })


async def create_checkout_session(*, order_number: str, email: str, amount: Decimal, currency: str,
                                  description: str, success_url: str, cancel_url: str) -> dict:
    form = checkout_form(order_number=order_number, email=email, amount=amount, currency=currency,
                         description=description, success_url=success_url, cancel_url=cancel_url)
    return await _call("POST", "/checkout/sessions", form, idempotency_key=f"checkout-{order_number}")


async def refund(*, payment_intent: str, amount: Decimal, order_number: str, already_refunded: Decimal) -> dict:
    """The idempotency key repeats for the same refund in the same state, so a retry after a timeout
    can't pay the customer twice."""
    form = encode_form({"payment_intent": payment_intent, "amount": to_cents(amount),
                        "metadata": {"order_number": order_number}})
    key = f"refund-{order_number}-{to_cents(already_refunded)}-{to_cents(amount)}"
    return await _call("POST", "/refunds", form, idempotency_key=key)
