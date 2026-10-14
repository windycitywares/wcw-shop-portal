"""Customers are people who paid for an order. They are grouped by email address (guest checkout has no account)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain import rfm
from app.domain.csvsafe import to_csv
from app.domain.money import q2
from app.models.commerce import Coupon
from app.schemas.customers import (
    CustomerCoupon,
    CustomerDetail,
    CustomerListOut,
    CustomerOrder,
    CustomerRow,
    SegmentSummary,
)
from app.services.auth import SERVICE_ONLY_SOURCES
from app.services.promotions import coupon_status

CUSTOMERS_SQL = text("""
SELECT lower(o.email) AS email,
       (array_agg(o.customer_name ORDER BY o.paid_at DESC) FILTER (WHERE o.customer_name IS NOT NULL))[1] AS name,
       count(*)::int AS orders,
       COALESCE(sum(o.grand_total - o.refunded_total), 0) AS revenue,
       min(o.paid_at) AS first_order_at,
       max(o.paid_at) AS last_order_at,
       bool_or(o.user_id IS NOT NULL) AS has_account,
       bool_or(n.id IS NOT NULL AND n.unsubscribed_at IS NULL AND n.source <> ALL(CAST(:service_only AS text[]))) AS subscribed
FROM orders o
LEFT JOIN newsletter_subscribers n ON n.email = lower(o.email)
WHERE o.paid_at IS NOT NULL AND o.status NOT IN ('cancelled', 'refunded')
  AND (CAST(:email AS text) IS NULL OR lower(o.email) = CAST(:email AS text))
GROUP BY lower(o.email)
""")

SUBSCRIBERS_WITHOUT_ORDERS_SQL = text("""
SELECT count(*)::int FROM newsletter_subscribers n
WHERE n.unsubscribed_at IS NULL AND n.source <> ALL(CAST(:service_only AS text[]))
  AND NOT EXISTS (SELECT 1 FROM orders o WHERE lower(o.email) = n.email AND o.paid_at IS NOT NULL AND o.status NOT IN ('cancelled', 'refunded'))
""")

SORTS = ("revenue", "orders", "recent", "oldest", "name")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CustomerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _all(self, email: str | None = None) -> list[CustomerRow]:
        rows = (await self.session.execute(CUSTOMERS_SQL, {"service_only": list(SERVICE_ONLY_SOURCES), "email": email})).mappings().all()
        stats = [rfm.CustomerStats(r["email"], r["orders"], Decimal(r["revenue"]), r["last_order_at"]) for r in rows]
        # A single customer is always judged against the whole customer base (VIP is a rank).
        segments = rfm.segment_all(stats, utcnow()) if email is None else await self._segment_for(stats)
        return [
            CustomerRow(
                email=r["email"], name=r["name"], orders=r["orders"], revenue=q2(Decimal(r["revenue"])),
                average_order=q2(Decimal(r["revenue"]) / r["orders"]) if r["orders"] else Decimal("0.00"),
                first_order_at=r["first_order_at"], last_order_at=r["last_order_at"], segment=segments[r["email"]],
                subscribed=bool(r["subscribed"]), has_account=bool(r["has_account"]),
            )
            for r in rows
        ]

    async def everyone(self) -> list[CustomerRow]:
        return await self._all()

    async def _segment_for(self, mine: list[rfm.CustomerStats]) -> dict[str, str]:
        everyone = (await self.session.execute(CUSTOMERS_SQL, {"service_only": list(SERVICE_ONLY_SOURCES), "email": None})).mappings().all()
        cutoff = rfm.vip_cutoff([Decimal(r["revenue"]) for r in everyone])
        now = utcnow()
        return {c.key: rfm.segment_of(c, now, cutoff) for c in mine}

    async def list(self, q: str | None, segment: str | None, sort: str, page: int, page_size: int) -> CustomerListOut:
        customers = await self._all()
        summary = []
        for key in rfm.SEGMENTS:
            members = [c for c in customers if c.segment == key]
            summary.append(SegmentSummary(
                key=key, label=rfm.SEGMENT_LABELS[key], help=rfm.SEGMENT_HELP[key], customers=len(members),
                revenue=q2(sum((c.revenue for c in members), Decimal(0))),
            ))
        shown = customers
        if segment:
            shown = [c for c in shown if c.segment == segment]
        if q:
            needle = q.strip().lower()
            shown = [c for c in shown if needle in c.email or needle in (c.name or "").lower()]
        order = {
            "revenue": lambda c: (-c.revenue, c.email),
            "orders": lambda c: (-c.orders, c.email),
            "recent": lambda c: (-c.last_order_at.timestamp(), c.email),
            "oldest": lambda c: (c.last_order_at.timestamp(), c.email),
            "name": lambda c: ((c.name or c.email).lower(), c.email),
        }[sort if sort in SORTS else "revenue"]
        shown = sorted(shown, key=order)
        start = (page - 1) * page_size
        without = (await self.session.execute(SUBSCRIBERS_WITHOUT_ORDERS_SQL, {"service_only": list(SERVICE_ONLY_SOURCES)})).scalar_one()
        return CustomerListOut(
            items=shown[start : start + page_size], total=len(shown), page=page, page_size=page_size, segments=summary,
            total_customers=len(customers), subscribers_without_orders=without,
        )

    async def export_csv(self, q: str | None, segment: str | None, sort: str) -> str:
        listing = await self.list(q, segment, sort, 1, 1_000_000)
        header = ["Email", "Name", "Segment", "Orders", "Total spent", "Average order", "First order", "Last order", "Marketing email", "Has account"]
        return to_csv(header, [
            (c.email, c.name, rfm.SEGMENT_LABELS[c.segment], c.orders, c.revenue, c.average_order, c.first_order_at, c.last_order_at,
             c.subscribed, c.has_account) for c in listing.items
        ])

    async def detail(self, email: str) -> CustomerDetail:
        email = email.strip().lower()
        found = await self._all(email)
        if not found:
            raise NotFoundError("No paid orders for that customer yet")
        orders = (await self.session.execute(text("""
            SELECT id, number, status::text AS status, payment_status, grand_total, refunded_total, coupon_code, placed_at
            FROM orders WHERE lower(email) = :email ORDER BY placed_at DESC NULLS LAST, id DESC LIMIT 100
        """), {"email": email})).mappings().all()
        coupons = (await self.session.execute(
            select(Coupon).where(func.lower(Coupon.assigned_email) == email).order_by(Coupon.id.desc()).limit(50)
        )).scalars().all()
        refunded = (await self.session.execute(text(
            "SELECT COALESCE(sum(refunded_total), 0) FROM orders WHERE lower(email) = :email"), {"email": email})).scalar_one()
        sub = (await self.session.execute(text(
            "SELECT source, created_at, unsubscribed_at FROM newsletter_subscribers WHERE email = :email"), {"email": email})).mappings().first()
        reviews = (await self.session.execute(text("""
            SELECT count(*)::int FROM reviews r JOIN users u ON u.id = r.user_id WHERE lower(u.email) = :email
        """), {"email": email})).scalar_one()
        role = (await self.session.execute(text("SELECT role::text FROM users WHERE lower(email) = :email"), {"email": email})).scalar_one_or_none()
        now = utcnow()
        coupon_rows = [
            CustomerCoupon(code=c.code, kind=c.kind, value=c.value, status=coupon_status(c, now), source=c.source, expires_at=c.expires_at)
            for c in coupons
        ]
        subscription = None
        if sub is not None and sub["source"] not in SERVICE_ONLY_SOURCES:
            subscription = {"status": "unsubscribed" if sub["unsubscribed_at"] else "subscribed", "source": sub["source"], "since": sub["created_at"].isoformat()}
        return CustomerDetail(
            summary=found[0], refunded=q2(Decimal(refunded)), orders=[CustomerOrder(**o) for o in orders], coupons=coupon_rows,
            subscription=subscription, reviews=reviews, account_role=role,
        )

