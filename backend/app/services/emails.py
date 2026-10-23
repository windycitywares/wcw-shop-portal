"""The email outbox: every email is saved first, then sent, so a failed send is retried instead of lost.

`enqueue` only adds the row (it commits together with whatever caused the email, such as an order).
`deliver` sends rows right away and records the result, and `process_outbox` (cron) retries the rest.
"""

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import mailer
from app.core.config import get_settings
from app.domain import emailtext
from app.models.commerce import EmailOutbox

log = logging.getLogger("wcw.emails")
MAX_ATTEMPTS = 5
MARKETING_KINDS = frozenset({"welcome_offer", "subscribe_confirmation", "abandoned_cart", "review_request", "back_in_stock", "campaign"})


def localized_path(locale: str | None, path: str) -> str:
    return path if (locale or "en") == "en" else f"/{locale}{path}"


def site_link(path: str, locale: str | None = "en") -> str:
    return f"{get_settings().site_url.rstrip('/')}{localized_path(locale, path)}"


def unsubscribe_url(token: str, locale: str | None = "en") -> str:
    return f"{site_link('/unsubscribe', locale)}?token={token}"


def enqueue(
    session: AsyncSession,
    kind: str,
    to: str,
    ctx: dict,
    *,
    locale: str | None = "en",
    related_type: str | None = None,
    related_id: int | None = None,
    send_after: datetime | None = None,
) -> EmailOutbox:
    """Render the email and add it to the outbox (no commit)."""
    locale = emailtext.loc(locale)
    rendered = emailtext.render(kind, {**ctx, "locale": locale})
    row = EmailOutbox(
        to_email=to.strip().lower(), kind=kind, subject=rendered.subject[:300], body_text=rendered.text,
        body_html=rendered.html, locale=locale, related_type=related_type, related_id=related_id,
        send_after=send_after or datetime.now(timezone.utc), status="queued", attempts=0,
    )
    session.add(row)
    return row


_UNSUBSCRIBE_LINK = re.compile(r"https?://[^\s<>\"]+/unsubscribe\?token=[A-Za-z0-9_-]+")


def _headers(row: EmailOutbox) -> tuple[tuple[str, str], ...]:
    """Marketing mail carries a List-Unsubscribe header (taken from the unsubscribe link in the body)."""
    if row.kind not in MARKETING_KINDS:
        return ()
    found = _UNSUBSCRIBE_LINK.search(row.body_text or "")
    return (("List-Unsubscribe", f"<{found.group(0)}>"),) if found else ()


async def _send_row(row: EmailOutbox) -> None:
    row.attempts += 1
    try:
        await mailer.send(mailer.Mail(to=row.to_email, subject=row.subject, text=row.body_text, html=row.body_html,
                                      headers=_headers(row)))
    except mailer.MailError as exc:
        row.last_error = exc.message[:500]
        row.status = "failed" if row.attempts >= MAX_ATTEMPTS else "queued"
        log.warning("Email %s to %s not sent (attempt %s): %s", row.kind, row.to_email, row.attempts, exc.message)
    else:
        row.status, row.sent_at, row.last_error = "sent", datetime.now(timezone.utc), None


async def deliver(session: AsyncSession, rows: list[EmailOutbox]) -> None:
    """Send these (already committed) rows now and record the outcome."""
    for row in rows:
        await _send_row(row)
    await session.commit()


async def process_outbox(session: AsyncSession, limit: int = 50) -> dict[str, int]:
    """Cron: send queued emails that are due, oldest first. Safe to run twice at once (rows are locked)."""
    now = datetime.now(timezone.utc)
    rows = (
        await session.execute(
            select(EmailOutbox)
            .where(EmailOutbox.status == "queued", EmailOutbox.send_after <= now)
            .order_by(EmailOutbox.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars().all()
    for row in rows:
        await _send_row(row)
    await session.commit()
    return {"sent": sum(1 for r in rows if r.status == "sent"), "retry": sum(1 for r in rows if r.status == "queued"),
            "failed": sum(1 for r in rows if r.status == "failed")}
