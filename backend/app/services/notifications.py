"""Admin bell: recent activity across the shop, each item linking to the page where it's handled.

Nothing is stored per event: the feed is read from the tables that already hold the activity (orders, refunds,
contact messages, stock requests, reviews, sign-ups, newsletter subscribers, failed backups). Each person only sees the kinds their role
can act on, and anything newer than `users.notifications_seen_at` counts as unread.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, has_permission
from app.domain.contacts import SERVICE_ONLY_SOURCES
from app.models.user import User

WINDOW_DAYS = 30
PAID_STATES = ("paid", "partially_refunded", "refunded")  # as in services/orders.py
MAX_UNREAD = 99

# Every source returns the same columns: type, ref (id), at, title, detail, extra, state.
SOURCES: dict[str, tuple[Permission, str]] = {
    "order": (Permission.ORDERS_MANAGE, """
        SELECT 'order' AS type, o.id::text AS ref, COALESCE(o.placed_at, o.created_at) AS at, o.number::text AS title,
               COALESCE(o.customer_name, o.email)::text AS detail, o.grand_total::text AS extra,
               CASE WHEN o.status = 'cancelled' THEN 'cancelled' ELSE o.payment_status::text END AS state
        FROM orders o WHERE COALESCE(o.placed_at, o.created_at) >= :since"""),
    "refund": (Permission.ORDERS_MANAGE, """
        SELECT 'refund', o.id::text, p.created_at, o.number::text, COALESCE(o.customer_name, o.email)::text, p.amount::text, p.status::text
        FROM payments p JOIN orders o ON o.id = p.order_id
        WHERE p.kind = 'refund' AND p.created_at >= :since"""),
    "message": (Permission.MESSAGES_MANAGE, """
        SELECT 'message', m.id::text, m.created_at, m.subject::text, m.name::text, NULL::text, m.status::text
        FROM contact_messages m WHERE m.created_at >= :since AND m.status <> 'spam'"""),
    "stock_request": (Permission.CUSTOMERS_VIEW, """
        SELECT 'stock_request', a.id::text, a.created_at, COALESCE(root.title, p.title)::text, a.email::text, a.kind::text,
               CASE WHEN a.notified_at IS NOT NULL THEN 'notified' WHEN a.closed_at IS NOT NULL THEN 'closed' ELSE 'waiting' END
        FROM stock_alerts a JOIN products p ON p.id = a.product_id LEFT JOIN products root ON root.id = p.parent_id
        WHERE a.created_at >= :since"""),
    "review": (Permission.REVIEWS_MODERATE, """
        SELECT 'review', r.id::text, r.created_at, p.title::text, r.author_name::text, r.rating::text, r.status::text
        FROM reviews r JOIN products p ON p.id = r.product_id WHERE r.created_at >= :since"""),
    "signup": (Permission.CUSTOMERS_VIEW, """
        SELECT 'signup', u.id::text, u.created_at, u.email::text, u.full_name::text, NULL::text, NULL::text
        FROM users u WHERE u.role = 'customer' AND u.created_at >= :since"""),
    "subscriber": (Permission.CUSTOMERS_VIEW, """
        SELECT 'subscriber', s.id::text, s.created_at, s.email::text, s.source::text, NULL::text, NULL::text
        FROM newsletter_subscribers s
        WHERE s.created_at >= :since AND s.source <> ALL(CAST(:service_only AS text[]))"""),
    "backup_failed": (Permission.BACKUPS_MANAGE, """
        SELECT 'backup_failed', b.id::text, b.started_at, COALESCE(b.file_name, 'Backup')::text, b.error::text, NULL::text, b.status::text
        FROM backup_runs b WHERE b.status = 'failed' AND b.started_at >= :since"""),
}


def allowed_sources(user: User) -> list[str]:
    return [name for name, (perm, _) in SOURCES.items() if has_permission(user.role, perm)]


def _money(value: str | None) -> str:
    try:
        return f"${float(value or 0):,.2f}"
    except ValueError:
        return ""


def present(row: dict[str, Any]) -> dict[str, Any]:
    """Turn a raw row into what the bell shows: a sentence, a second line and where clicking goes."""
    t, ref, title, detail, extra, state = row["type"], row["ref"], row["title"], row["detail"], row["extra"], row["state"]
    if t == "order":
        # The state is the order's payment now, not when it was placed: a refunded order was still paid for.
        if state == "cancelled":
            return {"title": f"Cancelled order {title}", "detail": f"{detail} · {_money(extra)}", "href": f"/admin/orders/{ref}", "tone": "neutral"}
        paid = state in PAID_STATES
        return {"title": f"{'New order' if paid else 'Order waiting for payment'} {title}", "detail": f"{detail} · {_money(extra)}",
                "href": f"/admin/orders/{ref}", "tone": "success" if paid else "warning"}
    if t == "refund":
        return {"title": f"Refund on {title}", "detail": f"{detail} · {_money(extra)}", "href": f"/admin/orders/{ref}", "tone": "danger"}
    if t == "message":
        return {"title": f"Message: {title}", "detail": f"From {detail}", "href": f"/admin/messages?id={ref}",
                "tone": "accent" if state == "new" else "neutral"}
    if t == "stock_request":
        special = extra == "request"
        return {"title": f"{'Special request' if special else 'Back-in-stock request'}: {title}", "detail": detail,
                "href": "/admin/stock-requests" if special else "/admin/stock-requests?view=restock", "tone": "accent" if special else "info"}
    if t == "review":
        return {"title": f"{extra}★ review of {title}", "detail": f"By {detail}" + (" · waiting for approval" if state == "pending" else ""),
                "href": "/admin/reviews?status=pending" if state == "pending" else "/admin/reviews?status=approved",
                "tone": "warning" if state == "pending" else "neutral"}
    if t == "subscriber":
        where = {"site": "the website form", "checkout": "checkout", "account": "their account", "admin": "added by staff"}.get(detail, detail)
        return {"title": "New newsletter subscriber", "detail": f"{title} · from {where}", "href": f"/admin/subscribers?q={title}", "tone": "info"}
    if t == "signup":
        return {"title": "New customer account", "detail": f"{detail + ' · ' if detail else ''}{title}",
                "href": f"/admin/customers?q={title}", "tone": "info"}
    return {"title": "A backup failed", "detail": (detail or "")[:160], "href": "/admin/backups", "tone": "danger"}


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _union(self, user: User, kinds: list[str] | None) -> str | None:
        names = [n for n in allowed_sources(user) if not kinds or n in kinds]
        cols = "(type, ref, at, title, detail, extra, state)"  # same names whichever source comes first
        return " UNION ALL ".join(f"SELECT * FROM ({SOURCES[n][1]}) AS s_{n}{cols}" for n in names) if names else None

    async def feed(self, user: User, limit: int = 20, kinds: list[str] | None = None, before: datetime | None = None) -> dict[str, Any]:
        since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
        union = self._union(user, kinds)
        seen = user.notifications_seen_at
        if union is None:
            return {"items": [], "unread": 0, "seen_at": seen, "kinds": []}
        cond = "WHERE at < :before" if before else ""
        rows = (await self.session.execute(
            text(f"SELECT * FROM ({union}) AS feed {cond} ORDER BY at DESC, ref DESC LIMIT :n"),
            {"since": since, "service_only": list(SERVICE_ONLY_SOURCES), "n": limit, **({"before": before} if before else {})},
        )).mappings().all()
        unread = (await self.session.execute(
            text(f"SELECT count(*) FROM ({self._union(user, None)}) AS feed WHERE at > :seen"),
            {"since": since, "service_only": list(SERVICE_ONLY_SOURCES), "seen": seen or since},
        )).scalar_one()
        items = [
            {"id": f"{r['type']}:{r['ref']}", "type": r["type"], "at": r["at"], "unread": seen is None or r["at"] > seen, **present(dict(r))}
            for r in rows
        ]
        return {"items": items, "unread": min(int(unread), MAX_UNREAD), "seen_at": seen, "kinds": allowed_sources(user)}

    async def mark_seen(self, user: User) -> None:
        await self.session.execute(text("UPDATE users SET notifications_seen_at = now() WHERE id = :id"), {"id": user.id})
        await self.session.commit()
