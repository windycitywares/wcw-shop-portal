"""Customer segments from purchase history (recency, frequency, value).

Memorial products are usually bought once, so the segments are written for that reality: "Active" and
"Loyal" are rare and valuable, "Lapsed" is not an emergency, and a one-time buyer is still welcome.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

SEGMENTS = ("vip", "loyal", "new", "active", "needs_nudge", "at_risk", "lapsed")

SEGMENT_LABELS = {
    "vip": "VIP",
    "loyal": "Loyal",
    "new": "New",
    "active": "Active",
    "needs_nudge": "Needs a nudge",
    "at_risk": "At risk",
    "lapsed": "Lapsed",
}

SEGMENT_HELP = {
    "vip": "Top 10% by total spend (at least 3 customers).",
    "loyal": "3 or more orders, the latest within 180 days.",
    "new": "First order within the last 60 days.",
    "active": "2 or more orders, the latest within 180 days.",
    "needs_nudge": "One order, placed 60-180 days ago.",
    "at_risk": "2 or more orders, the latest 180-365 days ago.",
    "lapsed": "Latest order more than a year ago.",
}


@dataclass(frozen=True)
class CustomerStats:
    key: str  # email
    orders: int
    revenue: Decimal
    last_order_at: datetime


def days_since(moment: datetime, now: datetime) -> int:
    return max(0, (now - moment).days)


def segment_of(stats: CustomerStats, now: datetime, vip_cutoff: Decimal | None = None) -> str:
    age = days_since(stats.last_order_at, now)
    if vip_cutoff is not None and stats.revenue >= vip_cutoff and stats.orders >= 1:
        return "vip"
    if stats.orders >= 3 and age <= 180:
        return "loyal"
    if stats.orders == 1 and age <= 60:
        return "new"
    if stats.orders >= 2 and age <= 180:
        return "active"
    if stats.orders == 1 and age <= 180:
        return "needs_nudge"
    if stats.orders >= 2 and age <= 365:
        return "at_risk"
    return "lapsed" if age > 365 or stats.orders == 1 else "at_risk"


def vip_cutoff(revenues: list[Decimal]) -> Decimal | None:
    """Spend needed to be in the top 10% (None when there are too few customers to say)."""
    if len(revenues) < 10:
        return None
    ordered = sorted(revenues, reverse=True)
    top = max(3, len(ordered) // 10)
    cutoff = ordered[top - 1]
    return cutoff if cutoff > 0 else None


def segment_all(customers: list[CustomerStats], now: datetime) -> dict[str, str]:
    cutoff = vip_cutoff([c.revenue for c in customers])
    return {c.key: segment_of(c, now, cutoff) for c in customers}
