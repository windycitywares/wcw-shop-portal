"""Stripe Checkout over plain HTTPS (no SDK needed): create a session, read it back, refund, verify webhooks."""

import asyncio
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.domain.money import to_cents
from app.services.payments.base import PaymentStart, ProviderError

log = logging.getLogger("wcw.stripe")
API_VERSION = "2024-06-20"
WEBHOOK_TOLERANCE_SECONDS = 300


def encode_form(data: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """Stripe's nested form encoding: {"a": {"b": [1, 2]}} -> a[b][0]=1&a[b][1]=2."""
    pairs: list[tuple[str, str]] = []
    for key, value in data.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if value is None:
            continue
        if isinstance(value, dict):
            pairs += encode_form(value, name)
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    pairs += encode_form(item, f"{name}[{i}]")
                else:
                    pairs.append((f"{name}[{i}]", str(item)))
        elif isinstance(value, bool):
            pairs.append((name, "true" if value else "false"))
        else:
            pairs.append((name, str(value)))
    return pairs


def verify_signature(payload: bytes, header: str | None, secret: str, now: float | None = None,
                     tolerance: int = WEBHOOK_TOLERANCE_SECONDS) -> bool:
    """Check a `Stripe-Signature` header (t=timestamp,v1=hex hmac) against the raw request body."""
    if not header or not secret:
        return False
    timestamp = ""
    signatures: list[str] = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if not timestamp.isdigit() or not signatures:
        return False
    if abs((now if now is not None else time.time()) - int(timestamp)) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in signatures)


def checkout_line_items(order, currency: str) -> list[dict[str, Any]]:
    """One Stripe line per order item (net of discounts), plus shipping and tax, adding up to the order total."""
    lines: list[dict[str, Any]] = []

    def add(name: str, cents: int) -> None:
        if cents > 0:
            lines.append({"quantity": 1, "price_data": {"currency": currency, "unit_amount": cents,
                                                         "product_data": {"name": name[:240]}}})

    for item in order.items:
        net = to_cents(item.line_total) - to_cents(item.discount_total)
        add(f"{item.title} × {item.quantity}" if item.quantity > 1 else item.title, net)
    add("Shipping", to_cents(order.shipping_total))
    add("Sales tax", to_cents(order.tax_total))
    total = sum(l["price_data"]["unit_amount"] for l in lines)
    if total != to_cents(order.grand_total):  # never send Stripe a different total than we show: fall back to one line
        lines = [{"quantity": 1, "price_data": {"currency": currency, "unit_amount": to_cents(order.grand_total),
                                                 "product_data": {"name": f"Order {order.number}"}}}]
    return lines


def _request(method: str, path: str, data: dict[str, Any] | None, secret: str, idempotency_key: str | None) -> dict[str, Any]:
    base = get_settings().stripe_api_base.rstrip("/")
    body = urllib.parse.urlencode(encode_form(data or {})).encode() if method == "POST" else None
    url = f"{base}{path}" + (f"?{urllib.parse.urlencode(encode_form(data or {}))}" if method == "GET" and data else "")
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {secret}")
    req.add_header("Stripe-Version", API_VERSION)
    req.add_header("User-Agent", "WindyCityWares/1.0")
    if idempotency_key:
        req.add_header("Idempotency-Key", idempotency_key)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 - fixed https base URL
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("error", {}).get("message", "")
        except (ValueError, OSError):
            detail = ""
        raise ProviderError(f"Stripe returned {exc.code}: {detail}") from exc
    except (OSError, ValueError) as exc:
        raise ProviderError(f"Could not reach Stripe: {exc}") from exc


def secret_key() -> str | None:
    """The live key normally; the Stripe test key while the app is in Test mode (never the live key there)."""
    from app.core import appmode

    settings = get_settings()
    return settings.stripe_test_secret_key if appmode.is_test() else settings.stripe_secret_key


async def api(method: str, path: str, data: dict[str, Any] | None = None, idempotency_key: str | None = None) -> dict[str, Any]:
    secret = secret_key()
    if not secret:
        raise ProviderError("Stripe is not configured")
    return await asyncio.to_thread(_request, method, path, data, secret, idempotency_key)


class StripeProvider:
    name = "stripe"

    async def start(self, order, return_urls: dict[str, str], lang: str, attempt: int = 1) -> PaymentStart:
        stripe_locale = lang if lang in ("en", "es", "nl") else "auto"
        session = await api(
            "POST", "/v1/checkout/sessions",
            {
                "mode": "payment",
                "success_url": return_urls["success"],
                "cancel_url": return_urls["cancel"],
                "customer_email": order.email,
                "client_reference_id": order.number,
                "locale": stripe_locale,
                "line_items": checkout_line_items(order, order.currency.lower()),
                "metadata": {"order_id": order.id, "order_number": order.number},
                "payment_intent_data": {"metadata": {"order_id": order.id, "order_number": order.number}},
                "expires_at": int(time.time()) + 3600,
            },
            idempotency_key=f"checkout-{order.number}-{attempt}",
        )
        url = session.get("url")
        if not url or not session.get("id"):
            raise ProviderError("Stripe did not return a checkout URL")
        return PaymentStart(status="redirect", provider_ref=session["id"], redirect_url=url, raw={"session": session["id"]})

    async def retrieve_session(self, session_id: str) -> dict[str, Any]:
        return await api("GET", f"/v1/checkout/sessions/{urllib.parse.quote(session_id, safe='')}")

    async def expire_session(self, session_id: str) -> None:
        """Close an unpaid Checkout Session so it can't be paid after we cancel the order. Best effort."""
        try:
            await api("POST", f"/v1/checkout/sessions/{urllib.parse.quote(session_id, safe='')}/expire")
        except ProviderError as exc:
            log.info("Could not expire Stripe session %s: %s", session_id, exc)

    async def refund(self, order, amount: Decimal, reason: str | None) -> dict[str, Any]:
        if not order.payment_intent_id:
            raise ProviderError("This order has no Stripe payment to refund")
        result = await api(
            "POST", "/v1/refunds",
            {"payment_intent": order.payment_intent_id, "amount": to_cents(amount),
             "metadata": {"order_number": order.number, "reason": (reason or "")[:200]}},
        )
        return {"refund": result.get("id"), "status": result.get("status")}
