"""The dashboard: the few numbers that matter today, a trend, what needs attention, and the top suggestions."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.timeutil import DateRange
from app.services.reports import common as c
from app.services.reports import insights, inventory, products, sales, sql, traffic


async def new_customers(session: AsyncSession, rng: DateRange) -> int:
    return (await c.one(session, sql.FIRST_ORDERS, c.params(rng))).get("new_customers", 0)


def overview_kpis(sold: dict, sold_before: dict, visits: dict, visits_before: dict, fresh: int, fresh_before: int) -> list[c.Row]:
    cards = [
        c.kpi("net", "Net revenue", sold["net"], sold_before["net"], "money", "Order totals minus refunds made in the period."),
        c.kpi("orders", "Orders", sold["orders"], sold_before["orders"], "number", "Paid orders, not counting cancelled ones."),
        c.kpi("aov", "Average order", sold["aov"], sold_before["aov"], "money", "Gross sales divided by orders."),
        c.kpi("conversion_rate", "Conversion rate", visits["conversion_rate"], visits_before["conversion_rate"], "percent",
              "Share of visits that placed an order (only visitors who accepted analytics are counted)."),
        c.kpi("visitors", "Visitors", visits["visitors"], visits_before["visitors"], "number", "Different browsers that visited (accepted analytics only)."),
        c.kpi("new_customers", "New customers", fresh, fresh_before, "number", "People whose first paid order fell in this period."),
    ]
    if (sold["cost_coverage"] or 0) > 0:
        cards.append(c.kpi("profit", "Estimated profit", sold["profit"], sold_before["profit"], "money", "Items sold minus their cost price (items with a cost price only)."))
    else:
        cards.append(c.kpi("units", "Items sold", sold["units"], sold_before["units"], "number"))
    cards.append(c.kpi("refund_rate", "Refund rate", sold["refund_rate"], sold_before["refund_rate"], "percent", "Refunds as a share of gross sales.", "down"))
    return cards


def attention(to_ship: int, late: int, awaiting: int, pending_reviews: int, summary: dict[str, Any]) -> list[c.Row]:
    """Things that need a person today, most urgent first. Only items with something to do are listed."""
    items = [
        {"key": "late", "label": "Paid orders waiting 2+ days to ship", "count": late, "href": "/admin/orders?status=paid", "tone": "critical"},
        {"key": "to_ship", "label": "Orders ready to ship", "count": to_ship, "href": "/admin/orders?status=paid", "tone": "warning"},
        {"key": "awaiting", "label": "Orders waiting for payment", "count": awaiting, "href": "/admin/orders?status=pending", "tone": "info"},
        {"key": "out_of_stock", "label": "Products out of stock", "count": summary.get("out", 0), "href": "/admin/analytics/inventory", "tone": "warning"},
        {"key": "low_stock", "label": "Products running low", "count": summary.get("low", 0), "href": "/admin/analytics/inventory", "tone": "info"},
        {"key": "reviews", "label": "Reviews to approve", "count": pending_reviews, "href": "/admin/reviews?status=pending", "tone": "info"},
    ]
    return [i for i in items if i["count"]]


async def report(
    session: AsyncSession, rng: DateRange, *, setup: dict[str, bool], low_threshold: int, free_threshold: Decimal | None, now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    before = rng.previous()
    p = c.params(rng)
    sold, sold_before = await sales.totals(session, rng), await sales.totals(session, before)
    visits, visits_before = await traffic.totals(session, rng), await traffic.totals(session, before)
    series = await sales.sales_series(session, rng)
    visit_series = c.fill_series(rng, await c.rows(session, sql.TRAFFIC_SERIES, p), {"sessions": 0, "visitors": 0})
    for point, visit in zip(series, visit_series, strict=True):
        point["sessions"], point["visitors"] = visit["sessions"], visit["visitors"]
    channels = traffic.channel_rows(await c.rows(session, sql.TRAFFIC_BY_CHANNEL, p))
    stock_rows = inventory.build_rows(await c.rows(session, sql.STOCK_LEVELS), low_threshold)
    stock = inventory.summary(stock_rows)
    product_rows = await products.table(session, rng)
    pending = await c.scalar(session, sql.WAITING_REVIEWS) or 0
    suggestions = await insights.suggestions(
        session, rng, setup=setup, low_threshold=low_threshold, free_threshold=free_threshold, now=now,
        sold=sold, visits=visits, product_rows=product_rows, stock=stock_rows,
    )
    return {
        "range": c.range_info(rng),
        "kpis": overview_kpis(sold, sold_before, visits, visits_before, await new_customers(session, rng), await new_customers(session, before)),
        "series": series,
        "channels": channels[:6],
        "top_products": [
            {"id": r["id"], "title": r["title"], "slug": r["slug"], "units": r["units"], "merchandise": r["merchandise"], "share": r["revenue_share"]}
            for r in product_rows if r["units"] > 0
        ][:5],
        "attention": attention(
            await c.scalar(session, sql.TO_SHIP) or 0, await c.scalar(session, sql.UNSHIPPED) or 0,
            (await c.one(session, sql.PAYMENTS_WAITING)).get("n", 0), pending, stock,
        ),
        "live_visitors": await c.scalar(session, sql.LIVE_NOW) or 0,
        "recent_orders": [
            {**r, "grand_total": c.num(r["grand_total"])} for r in c.clean_all(await c.rows(session, sql.RECENT_ORDERS))
        ],
        "suggestions": suggestions[:4],
        "suggestion_count": len(suggestions),
        "generated_at": now.isoformat(),
    }
