"""Customers, one row per email address: everyone who paid for an order (guest checkout included) and every
shopper who signed up, even before a first order. Buyers are grouped by how they buy (RFM); people with an
account and no paid order yet are their own group. Campaign audiences use buyers only (`everyone()`).
"""

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

ACCOUNTS_SQL = text("""
SELECT u.id, lower(u.email) AS email, u.full_name AS name, u.is_active, u.created_at,
       bool_or(n.id IS NOT NULL AND n.unsubscribed_at IS NULL AND n.source <> ALL(CAST(:service_only AS text[]))) AS subscribed
FROM users u
LEFT JOIN newsletter_subscribers n ON n.email = lower(u.email)
WHERE u.role = 'customer' AND (CAST(:email AS text) IS NULL OR lower(u.email) = CAST(:email AS text))
GROUP BY u.id
""")

SORTS = ("revenue", "orders", "recent", "oldest", "name", "joined")
# Not a buying pattern: people who made an account but haven't paid for an order.
SIGNED_UP = "signed_up"
SIGNED_UP_LABEL = "Signed up, no order yet"
SIGNED_UP_HELP = "Made an account but haven't paid for an order. A welcome campaign is the nudge."
GROUPS = (*rfm.SEGMENTS, SIGNED_UP)
ACCOUNT_FILTERS = ("all", "account", "guest", "disabled")


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

    async def _people(self, email: str | None = None) -> list[CustomerRow]:
        """Buyers and shopper accounts together, one row per address."""
        buyers = await self._all(email)
        accounts = (await self.session.execute(
            ACCOUNTS_SQL, {"service_only": list(SERVICE_ONLY_SOURCES), "email": email})).mappings().all()
        by_email = {a["email"]: a for a in accounts}
        rows: list[CustomerRow] = []
        for b in buyers:
            a = by_email.pop(b.email, None)
            if a is not None:
                b = b.model_copy(update={
                    "has_account": True, "account_id": a["id"], "account_active": a["is_active"], "joined_at": a["created_at"],
                    "name": b.name or a["name"],
                })
            rows.append(b)
        for a in by_email.values():
            rows.append(CustomerRow(
                email=a["email"], name=a["name"], orders=0, revenue=Decimal("0.00"), average_order=Decimal("0.00"),
                first_order_at=None, last_order_at=None, segment=SIGNED_UP, subscribed=bool(a["subscribed"]),
                has_account=True, account_id=a["id"], account_active=a["is_active"], joined_at=a["created_at"],
            ))
        return rows

    async def _segment_for(self, mine: list[rfm.CustomerStats]) -> dict[str, str]:
        everyone = (await self.session.execute(CUSTOMERS_SQL, {"service_only": list(SERVICE_ONLY_SOURCES), "email": None})).mappings().all()
        cutoff = rfm.vip_cutoff([Decimal(r["revenue"]) for r in everyone])
        now = utcnow()
        return {c.key: rfm.segment_of(c, now, cutoff) for c in mine}

    async def list(
        self, q: str | None, segment: str | None, sort: str, page: int, page_size: int, account: str = "all",
    ) -> CustomerListOut:
        customers = await self._people()
        summary = []
        for key in GROUPS:
            members = [c for c in customers if c.segment == key]
            summary.append(SegmentSummary(
                key=key, label=rfm.SEGMENT_LABELS.get(key, SIGNED_UP_LABEL), help=rfm.SEGMENT_HELP.get(key, SIGNED_UP_HELP),
                customers=len(members), revenue=q2(sum((c.revenue for c in members), Decimal(0))),
            ))
        shown = customers
        if segment:
            shown = [c for c in shown if c.segment == segment]
        if account == "account":
            shown = [c for c in shown if c.account_id is not None]
        elif account == "guest":
            shown = [c for c in shown if c.account_id is None]
        elif account == "disabled":
            shown = [c for c in shown if c.account_active is False]
        if q:
            needle = q.strip().lower()
            shown = [c for c in shown if needle in c.email or needle in (c.name or "").lower()]
        # People who never ordered go last when sorting by order dates.
        order = {
            "revenue": lambda c: (-c.revenue, c.email),
            "orders": lambda c: (-c.orders, c.email),
            "recent": lambda c: (c.last_order_at is None, -(c.last_order_at.timestamp() if c.last_order_at else 0), c.email),
            "oldest": lambda c: (c.last_order_at is None, c.last_order_at.timestamp() if c.last_order_at else 0, c.email),
            "name": lambda c: ((c.name or c.email).lower(), c.email),
            "joined": lambda c: (c.joined_at is None, -(c.joined_at.timestamp() if c.joined_at else 0), c.email),
        }[sort if sort in SORTS else "revenue"]
        shown = sorted(shown, key=order)
        start = (page - 1) * page_size
        without = (await self.session.execute(SUBSCRIBERS_WITHOUT_ORDERS_SQL, {"service_only": list(SERVICE_ONLY_SOURCES)})).scalar_one()
        return CustomerListOut(
            items=shown[start : start + page_size], total=len(shown), page=page, page_size=page_size, segments=summary,
            total_customers=sum(1 for c in customers if c.orders > 0),
            accounts_without_orders=sum(1 for c in customers if c.segment == SIGNED_UP), subscribers_without_orders=without,
        )

    async def export_csv(self, q: str | None, segment: str | None, sort: str, account: str = "all") -> str:
        listing = await self.list(q, segment, sort, 1, 1_000_000, account)
        header = ["Email", "Name", "Segment", "Orders", "Total spent", "Average order", "First order", "Last order", "Marketing email",
                  "Account"]
        return to_csv(header, [
            (c.email, c.name, rfm.SEGMENT_LABELS.get(c.segment, SIGNED_UP_LABEL), c.orders, c.revenue, c.average_order, c.first_order_at,
             c.last_order_at, c.subscribed, _account_label(c)) for c in listing.items
        ])

    async def detail(self, email: str) -> CustomerDetail:
        email = email.strip().lower()
        found = await self._people(email)
        if not found:
            raise NotFoundError("No orders or account for that customer")
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



def _account_label(c: CustomerRow) -> str:
    if c.account_id is None:
        return "staff" if c.has_account else "guest"
    return "active" if c.account_active else "switched off"
