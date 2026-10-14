"""Sales: revenue, orders, discounts, refunds, profit, and when/where/how people buy."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.timeutil import DateRange
from app.services.reports import common as c
from app.services.reports import sql

WEEKDAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")  # PostgreSQL's extract(dow) numbering
ORDER_BANDS = {1: "Under $50", 2: "$50-99", 3: "$100-199", 4: "$200-299", 5: "$300 and over"}


async def totals(session: AsyncSession, rng: DateRange) -> dict[str, Any]:
    """Every headline sales number for one period (used for the report, the previous-period comparison and the insights)."""
    p = c.params(rng)
    sales = await c.one(session, sql.SALES_KPIS, p)
    refunds = await c.one(session, sql.REFUNDS, p)
    items = await c.one(session, sql.ITEM_KPIS, p)
    orders = sales.get("orders", 0)
    gross = c.num(sales.get("gross"))
    refunded = c.num(refunds.get("refunds"))
    units = items.get("units", 0)
    merchandise = c.num(items.get("merchandise"))
    costed = c.num(items.get("costed_merchandise"))
    profit = c.num(items.get("profit"))
    subtotal = c.num(sales.get("items_subtotal"))
    discounts = c.num(sales.get("discounts"))
    return {
        "orders": orders,
        "gross": gross,
        "refunds": refunded,
        "refund_count": refunds.get("refund_count", 0),
        "net": round(gross - refunded, 2),
        "items_subtotal": subtotal,
        "discounts": discounts,
        "shipping": c.num(sales.get("shipping")),
        "tax": c.num(sales.get("tax")),
        "discounted_orders": sales.get("discounted_orders", 0),
        "customers": sales.get("customers", 0),
        "units": units,
        "units_refunded": items.get("units_refunded", 0),
        "merchandise": merchandise,
        "sale_savings": c.num(items.get("sale_savings")),
        "profit": profit,
        "costed_merchandise": costed,
        "lines": items.get("lines", 0),
        "lines_without_cost": items.get("lines_without_cost", 0),
        # shares and averages (None when there is nothing to divide by)
        "aov": c.avg(gross, orders),
        "units_per_order": c.avg(units, orders),
        "discount_rate": c.ratio(discounts, subtotal),
        "discount_share": c.ratio(sales.get("discounted_orders", 0), orders),
        "refund_rate": c.ratio(refunded, gross),
        "margin": c.ratio(profit, costed),
        "cost_coverage": c.ratio(costed, merchandise),
    }


def sales_kpis(now: dict[str, Any], before: dict[str, Any]) -> list[c.Row]:
    show_profit = (now["cost_coverage"] or 0) > 0 or (before["cost_coverage"] or 0) > 0
    cards = [
        c.kpi("net", "Net revenue", now["net"], before["net"], "money", "Order totals (items, shipping and tax) minus refunds made in the period."),
        c.kpi("gross", "Gross sales", now["gross"], before["gross"], "money", "Order totals before refunds. Counted on the day the order was paid."),
        c.kpi("orders", "Orders", now["orders"], before["orders"], "number", "Paid orders, not counting cancelled ones."),
        c.kpi("aov", "Average order value", now["aov"], before["aov"], "money", "Gross sales divided by orders."),
        c.kpi("units", "Items sold", now["units"], before["units"], "number", "Units across all paid orders."),
        c.kpi("discounts", "Discounts given", now["discounts"], before["discounts"], "money", "Sales, cart offers and coupons together.", "none"),
        c.kpi("refunds", "Refunds", now["refunds"], before["refunds"], "money", "Money returned in the period (counted when refunded).", "down"),
        c.kpi("refund_rate", "Refund rate", now["refund_rate"], before["refund_rate"], "percent", "Refunds as a share of gross sales.", "down"),
        c.kpi("shipping", "Shipping collected", now["shipping"], before["shipping"], "money", "", "none"),
        c.kpi("tax", "Sales tax collected", now["tax"], before["tax"], "money", "Collected for the state, not income.", "none"),
    ]
    if show_profit:
        cards.insert(4, c.kpi("profit", "Estimated profit", now["profit"], before["profit"], "money",
                              "Items sold minus their cost price (only items with a cost price are counted)."))
    return cards


def heatmap(found: list[c.Row]) -> dict[str, Any]:
    grid = [[0] * 24 for _ in range(7)]
    for r in found:
        grid[int(r["dow"])][int(r["hour"])] = int(r["orders"])
    order = (1, 2, 3, 4, 5, 6, 0)  # Monday first
    top = max((max(row) for row in grid), default=0)
    return {"days": [{"day": WEEKDAYS[d], "hours": grid[d]} for d in order], "max": top}


def order_sizes(found: list[c.Row]) -> list[c.Row]:
    by_band = {int(r["band"]): r for r in found}
    total = sum(int(r["orders"]) for r in found)
    return [
        {"band": ORDER_BANDS[b], "orders": int(by_band.get(b, {}).get("orders", 0)), "gross": c.num(by_band.get(b, {}).get("gross")),
         "share": c.ratio(by_band.get(b, {}).get("orders", 0), total)}
        for b in ORDER_BANDS
    ]


def discount_split(found: list[c.Row]) -> dict[str, Any]:
    out: dict[str, Any] = {"discounted": {"orders": 0, "gross": 0.0, "aov": None}, "full_price": {"orders": 0, "gross": 0.0, "aov": None}}
    for r in found:
        key = "discounted" if r["discounted"] else "full_price"
        out[key] = {"orders": int(r["orders"]), "gross": c.num(r["gross"]), "aov": c.num(r["aov"]) if r["orders"] else None}
    return out


async def sales_series(session: AsyncSession, rng: DateRange) -> list[c.Row]:
    p = c.params(rng)
    sold = {r["bucket"]: r for r in await c.rows(session, sql.SALES_SERIES, p)}
    refunded = {r["bucket"]: c.num(r["refunds"]) for r in await c.rows(session, sql.REFUND_SERIES, p)}
    gran = rng.granularity()
    series = []
    for day in c.bucket_starts(rng):
        row = sold.get(day, {})
        gross, refunds = c.num(row.get("gross")), refunded.get(day, 0.0)
        series.append({
            "bucket": day.isoformat(), "label": c.bucket_label(day, gran), "orders": row.get("orders", 0),
            "gross": gross, "refunds": refunds, "net": round(gross - refunds, 2),
        })
    return series


async def report(session: AsyncSession, rng: DateRange) -> dict[str, Any]:
    now = await totals(session, rng)
    before = await totals(session, rng.previous())
    p = c.params(rng)
    regions = await c.rows(session, sql.SALES_BY_REGION, p)
    gross_total = sum(c.num(r["gross"]) for r in regions) or None
    new_returning = await c.one(session, sql.FIRST_ORDERS, p)
    fulfil = await c.one(session, sql.FULFILLMENT, p)
    waiting = await c.one(session, sql.PAYMENTS_WAITING)
    return {
        "range": c.range_info(rng),
        "kpis": sales_kpis(now, before),
        "totals": now,
        "series": await sales_series(session, rng),
        "by_category": c.clean_all(await c.rows(session, sql.SALES_BY_CATEGORY, p)),
        "by_payment": c.clean_all(await c.rows(session, sql.SALES_BY_PAYMENT, p)),
        "by_region": [
            {"country": r["country"], "region": r["region"], "label": f"{r['region']}, {r['country']}", "orders": r["orders"], "gross": c.num(r["gross"]),
             "share": c.ratio(c.num(r["gross"]), gross_total)}
            for r in regions
        ],
        "heatmap": heatmap(await c.rows(session, sql.SALES_HEATMAP, p)),
        "order_sizes": order_sizes(await c.rows(session, sql.ORDER_SIZES, p)),
        "discount_split": discount_split(await c.rows(session, sql.DISCOUNT_SPLIT, p)),
        "new_returning": {
            "new_customers": new_returning.get("new_customers", 0),
            "returning_customers": new_returning.get("returning_customers", 0),
            "series": c.fill_series(rng, await c.rows(session, sql.NEW_VS_RETURNING_SERIES, p), {"new_orders": 0, "returning_orders": 0}),
        },
        "fulfillment": {
            "shipped": fulfil.get("shipped", 0),
            "hours_to_ship": c.num(fulfil.get("hours_to_ship"), 1),
            "days_in_transit": c.num(fulfil.get("days_in_transit"), 1),
            "unshipped_over_2d": await c.scalar(session, sql.UNSHIPPED) or 0,
            "awaiting_payment": waiting.get("n", 0),
            "awaiting_payment_value": c.num(waiting.get("value")),
        },
    }
