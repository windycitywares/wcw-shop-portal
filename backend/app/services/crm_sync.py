"""Send recorded changes to the CRM (docs/CRM_SYNC.md; the CRM's contract is its docs/SHOP_EVENTS.md).

Run by the `crm_sync` job. For each pending `crm_outbox` row it reads the order / account / subscriber /
contact message as it is now, wraps it in a signed event and posts it. Several rows for the same record are
sent once. The CRM ignores a re-sent event id, so a send that timed out after the CRM stored it is safe to
repeat.

Always works on the live data, whatever Admin → Test mode is set to.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import appmode
from app.core.config import get_settings
from app.core.enums import UserRole
from app.domain.contacts import SERVICE_ONLY_SOURCES
from app.models.account import ContactMessage
from app.models.contact import Contact
from app.models.crm import CrmOutbox
from app.models.order import Order
from app.models.user import NewsletterSubscriber, User

log = logging.getLogger("wcw.crm_sync")

BATCH = 100
TIME_BUDGET = 40.0  # seconds per run, so a slow CRM never holds up the other jobs
TIMEOUT = 10.0
MAX_ATTEMPTS = 12  # backoff 1, 2, 4 … minutes, capped at 6 hours: about two days of trying
KEEP_DAYS = 30
PERMANENT = {400, 413, 422}  # the CRM will never accept this body

# (status code or None for a network error, short text) — replaceable in tests.
Transport = Callable[[str, bytes, dict[str, str]], tuple[int | None, str]]


def _post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int | None, str]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:  # noqa: S310 - URL comes from the server config
            return res.status, res.read(500).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(500).decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


transport: Transport = _post


def sign(secret: str, timestamp: int, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _money(value: Decimal | None) -> str:
    return f"{(value or Decimal(0)):.2f}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def order_payload(o: Order) -> dict[str, Any]:
    """An order as the CRM reads it (events and the read API share this shape)."""
    return {
        "id": o.id, "number": o.number, "user_id": o.user_id, "email": o.email, "customer_name": o.customer_name,
        "phone": o.phone, "status": str(o.status), "payment_status": o.payment_status, "currency": o.currency,
        "grand_total": _money(o.grand_total), "refunded_total": _money(o.refunded_total),
        "placed_at": _iso(o.placed_at or o.created_at), "updated_at": _iso(o.updated_at),
        "marketing_opt_in": bool(o.marketing_opt_in),
        "billing_address": o.billing_address, "shipping_address": o.shipping_address,
    }


def customer_payload(u: User) -> dict[str, Any]:
    return {"id": u.id, "email": u.email, "full_name": u.full_name}


def contact_record_payload(c: Contact) -> dict[str, Any]:
    return {
        "id": c.id, "email": c.email, "full_name": c.full_name, "phone": c.phone,
        "source": c.source, "user_id": c.user_id, "marketing_opt_in": c.marketing_opt_in,
        "created_at": _iso(c.created_at), "updated_at": _iso(c.updated_at),
    }


def newsletter_event(s: NewsletterSubscriber) -> tuple[str, dict[str, Any]] | None:
    # `at` is when it happened here, so the CRM shows the real date and not the moment it heard about it.
    if s.unsubscribed_at is not None:
        return "newsletter.unsubscribed", {"email": s.email, "at": s.unsubscribed_at.isoformat()}
    if s.source in SERVICE_ONLY_SOURCES:
        return None  # a row kept only for service-email unsubscribe links: not a subscriber
    return "newsletter.subscribed", {"email": s.email, "source": s.source,
                                     "at": s.created_at.isoformat() if s.created_at else None}


def contact_payload(m: ContactMessage) -> dict[str, Any]:
    """A contact-form message: who wrote, and what they wrote. The CRM opens a ticket for it (SPEC 3.5).

    The form has no phone field, so none is sent; the CRM treats a missing one the same as an empty one.
    """
    return {"name": m.name, "email": m.email, "subject": m.subject, "message": m.message,
            "order_number": m.order_number}


class CrmSync:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ---- payloads ------------------------------------------------------------------------
    async def build(self, kind: str, ref_id: int) -> tuple[str, dict[str, Any]] | None:
        """(event type, data) for the record as it is now, or None when there is nothing to tell."""
        model = {"order": Order, "customer": User, "newsletter": NewsletterSubscriber,
                 "contact": ContactMessage, "contact_record": Contact}.get(kind)
        row = await self.session.get(model, ref_id) if model else None
        if row is None:
            return None
        if kind == "order":
            return "order.updated", order_payload(row)
        if kind == "customer":
            return ("customer.upserted", customer_payload(row)) if row.role == UserRole.CUSTOMER else None
        if kind == "contact_record":
            return "contact.upserted", contact_record_payload(row)
        if kind == "contact":
            return "contact_message.created", contact_payload(row)
        return newsletter_event(row)

    # ---- sending ---------------------------------------------------------------------------
    def _retry_later(self, rows: list[CrmOutbox], error: str, now: datetime) -> None:
        for row in rows:
            row.attempts += 1
            row.last_error = error[:1000]
            if row.attempts >= MAX_ATTEMPTS:
                row.status = "failed"
            else:
                row.next_attempt_at = now + timedelta(minutes=min(2 ** (row.attempts - 1), 360))

    async def deliver_due(self) -> dict[str, Any]:
        cfg = get_settings()
        if not cfg.crm_sync_enabled:
            return {"skipped": "not configured"}
        started, now = time.monotonic(), _now()
        counts = {"sent": 0, "skipped": 0, "retry": 0, "failed": 0}
        with appmode.use(appmode.LIVE):
            rows = list((await self.session.execute(
                select(CrmOutbox).where(CrmOutbox.status == "pending", CrmOutbox.next_attempt_at <= now)
                .order_by(CrmOutbox.id).limit(BATCH)
            )).scalars())
            groups: dict[tuple[str, int], list[CrmOutbox]] = {}
            for row in rows:
                groups.setdefault((row.kind, row.ref_id), []).append(row)

            for (kind, ref_id), group in groups.items():
                if time.monotonic() - started > TIME_BUDGET:
                    break
                latest, older = group[-1], group[:-1]
                for row in older:  # one send covers them all: it carries the current state
                    row.status, row.sent_at = "merged", now
                built = await self.build(kind, ref_id)
                if built is None:
                    latest.status, latest.sent_at = "skipped", now
                    counts["skipped"] += 1
                    continue
                event_type, data = built
                body = json.dumps({"id": f"shop-{latest.id}", "type": event_type, "occurred_at": _iso(latest.created_at),
                                   "data": data}, separators=(",", ":"), default=str).encode()
                ts = int(time.time())
                code, text = await asyncio.to_thread(transport, str(cfg.crm_webhook_url), body, {
                    "Content-Type": "application/json", "User-Agent": "wcw-shop/crm-sync",
                    "X-WCW-Timestamp": str(ts), "X-WCW-Signature": sign(str(cfg.crm_webhook_secret), ts, body),
                })
                if code == 200:
                    latest.status, latest.sent_at, latest.last_error = "sent", _now(), None
                    counts["sent"] += 1
                elif code in PERMANENT:
                    latest.status, latest.last_error = "failed", f"{code}: {text}"[:1000]
                    counts["failed"] += 1
                    log.warning("CRM refused %s %s: %s %s", kind, ref_id, code, text[:200])
                else:
                    self._retry_later([latest], f"{code or 'network'}: {text}", now)
                    counts["failed" if latest.status == "failed" else "retry"] += 1
                await self.session.commit()

            purged = (await self.session.execute(delete(CrmOutbox).where(
                CrmOutbox.status.in_(("sent", "skipped", "merged")), CrmOutbox.created_at < now - timedelta(days=KEEP_DAYS),
            ))).rowcount or 0
            await self.session.commit()
        if purged:
            counts["purged"] = purged
        return {k: v for k, v in counts.items() if v}
