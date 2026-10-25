"""The shopper's bell: what happened to their orders, newest first, and how much is unread.

Nothing is stored per event: an order already carries the times of its milestones (placed, paid,
shipped, delivered, cancelled), and a refund is a row in `payments`. The words are chosen in the
storefront so they arrive in the reader's language; this service only says what happened.

`users.notifications_seen_at` says how far the person has read. Staff use the same column for the
admin bell; a person is one or the other, and the two feeds are about the same life.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

WINDOW_DAYS = 365
MAX_UNREAD = 99
MAX_ITEMS = 50

# Every branch has the same columns: kind, order_id, number, token, at, extra (a refund amount).
FEED = text("""
WITH mine AS (
    SELECT id, number, access_token, placed_at, created_at, paid_at, shipped_at, delivered_at, cancelled_at
    FROM orders
    WHERE user_id = :uid AND COALESCE(placed_at, created_at) >= :since
)
SELECT * FROM (
    SELECT 'placed' AS kind, id AS order_id, number, access_token AS token,
           COALESCE(placed_at, created_at) AS at, NULL::text AS extra
    FROM mine
    UNION ALL
    SELECT 'paid', id, number, access_token, paid_at, NULL::text
    FROM mine
    WHERE paid_at IS NOT NULL AND paid_at > COALESCE(placed_at, created_at) + interval '1 hour'
    UNION ALL
    SELECT 'shipped', id, number, access_token, shipped_at, NULL::text
    FROM mine WHERE shipped_at IS NOT NULL
    UNION ALL
    SELECT 'delivered', id, number, access_token, delivered_at, NULL::text
    FROM mine WHERE delivered_at IS NOT NULL
    UNION ALL
    SELECT 'cancelled', id, number, access_token, cancelled_at, NULL::text
    FROM mine WHERE cancelled_at IS NOT NULL
    UNION ALL
    SELECT 'refunded', o.id, o.number, o.access_token, p.created_at, p.amount::text
    FROM payments p JOIN orders o ON o.id = p.order_id
    WHERE o.user_id = :uid AND p.kind = 'refund' AND p.created_at >= :since
) AS feed
ORDER BY at DESC, order_id DESC
LIMIT :n
""")


class AccountNotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def feed(self, user: User, limit: int = 20) -> dict[str, Any]:
        since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
        rows = (await self.session.execute(
            FEED, {"uid": user.id, "since": since, "n": min(limit, MAX_ITEMS)}
        )).mappings().all()
        seen = user.notifications_seen_at
        items = [
            {
                "id": f"{r['kind']}:{r['order_id']}",
                "kind": r["kind"],
                "order_id": r["order_id"],
                "number": r["number"],
                "token": r["token"],
                "at": r["at"],
                "amount": float(r["extra"]) if r["extra"] is not None else None,
                "unread": seen is None or r["at"] > seen,
            }
            for r in rows
        ]
        return {"items": items, "unread": min(sum(1 for item in items if item["unread"]), MAX_UNREAD)}

    async def pulse(self, user: User) -> dict[str, Any]:
        """The cheapest "anything new?" answer for the live bell: unread count and the newest milestone's time."""
        since = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
        rows = (await self.session.execute(
            FEED, {"uid": user.id, "since": since, "n": MAX_ITEMS}
        )).mappings().all()
        seen = user.notifications_seen_at
        unread = sum(1 for r in rows if seen is None or r["at"] > seen)
        latest = rows[0]["at"] if rows else None
        return {"unread": min(unread, MAX_UNREAD), "latest": latest.isoformat() if latest else None}

    async def mark_seen(self, user: User) -> None:
        await self.session.execute(
            text("UPDATE users SET notifications_seen_at = now() WHERE id = :id"), {"id": user.id}
        )
        await self.session.commit()
