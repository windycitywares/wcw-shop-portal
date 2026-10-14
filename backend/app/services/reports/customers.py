"""Customers: who buys, who comes back, what a customer is worth, and how the email list grows.

A *customer* is an email address with at least one paid order (guest checkout has no account).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import rfm
from app.domain.contacts import SERVICE_ONLY_SOURCES
from app.domain.timeutil import DateRange
from app.services.reports import common as c
from app.services.reports import sql


async def lifetime(session: AsyncSession) -> dict[str, Any]:
    """Whole-history customer numbers (they do not depend on the date range)."""
    t = await c.one(session, sql.CUSTOMER_TOTALS)
    gap = await c.one(session, sql.SECOND_ORDER_GAP)
    customers = t.get("customers", 0)
    return {
        "customers": customers, "repeat_customers": t.get("repeat_customers", 0),
        "repeat_rate": c.ratio(t.get("repeat_customers", 0), customers),
        "avg_lifetime_value": c.num(t.get("avg_lifetime_value")), "avg_orders": c.num(t.get("avg_orders")),
        "median_days_to_second_order": c.num(gap.get("median_days"), 0) if gap.get("n") else None, "second_orders": gap.get("n", 0),
    }


def segment_summary(rows: list[c.Row], now: datetime) -> list[c.Row]:
    stats = [rfm.CustomerStats(r["email"], r["orders"], Decimal(r["revenue"]), r["last_order_at"]) for r in rows]
    assigned = rfm.segment_all(stats, now)
    revenue = {s.key: s.revenue for s in stats}
    total_revenue = sum(revenue.values(), Decimal(0))
    out = []
    for key in rfm.SEGMENTS:
        members = [k for k, seg in assigned.items() if seg == key]
        spend = sum((revenue[k] for k in members), Decimal(0))
        out.append({
            "key": key, "label": rfm.SEGMENT_LABELS[key], "help": rfm.SEGMENT_HELP[key], "customers": len(members),
            "revenue": c.num(spend), "revenue_share": c.ratio(spend, total_revenue),
        })
    return out


def cohort_table(found: list[c.Row], through: date) -> list[c.Row]:
    """One row per first-purchase month: how many customers there were and how many bought again N months later."""
    by_cohort: dict[date, dict[int, int]] = {}
    for r in found:
        by_cohort.setdefault(r["cohort"], {})[int(r["months_later"])] = int(r["customers"])
    table = []
    for cohort in sorted(by_cohort):
        observable = (through.year - cohort.year) * 12 + through.month - cohort.month
        counts = by_cohort[cohort]
        size = counts.get(0, 0)
        returned = [counts.get(m, 0) for m in range(observable + 1)]
        table.append({
            "cohort": cohort.isoformat(), "label": cohort.strftime("%b %Y"), "size": size, "returned": returned,
            "retention": [c.ratio(n, size) for n in returned],
        })
    return table


async def report(session: AsyncSession, rng: DateRange, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    p = c.params(rng, service_only=list(SERVICE_ONLY_SOURCES))
    new_returning = await c.one(session, sql.FIRST_ORDERS, p)
    sales = await c.one(session, sql.SALES_KPIS, p)
    news = await c.one(session, sql.NEWSLETTER, p)
    return {
        "range": c.range_info(rng),
        "lifetime": await lifetime(session),
        "in_range": {
            "customers": sales.get("customers", 0),
            "new_customers": new_returning.get("new_customers", 0), "returning_customers": new_returning.get("returning_customers", 0),
            "new_share": c.ratio(new_returning.get("new_customers", 0), sales.get("customers", 0)),
        },
        "segments": segment_summary(await c.rows(session, sql.CUSTOMER_STATS), now),
        "new_vs_returning": c.fill_series(rng, await c.rows(session, sql.NEW_VS_RETURNING_SERIES, p), {"new_orders": 0, "returning_orders": 0}),
        "top_customers": [
            {"email": r["email"], "name": r["name"], "orders": r["orders"], "revenue": c.num(r["revenue"]), "last_order_at": r["last_order_at"].isoformat()}
            for r in await c.rows(session, sql.TOP_CUSTOMERS)
        ],
        "geo": [{"region": r["region"], "country": r["country"], "customers": r["customers"], "revenue": c.num(r["revenue"])} for r in await c.rows(session, sql.CUSTOMER_GEO, p)],
        "cohorts": cohort_table(await c.rows(session, sql.COHORTS, p), rng.end),
        "newsletter": {
            "subscribers": news.get("subscribers", 0), "joined": news.get("joined", 0), "left": news.get("left_list", 0),
            "net": news.get("joined", 0) - news.get("left_list", 0),
            "by_source": c.clean_all(await c.rows(session, sql.NEWSLETTER_BY_SOURCE, p)),
        },
    }
