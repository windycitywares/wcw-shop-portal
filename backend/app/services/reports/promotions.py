"""Promotions: what sales, coupons, automatic offers, campaigns and cart reminders cost and what they bring back."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.cart_rules import ACTIVE_WINDOW
from app.domain.timeutil import DateRange
from app.services.reports import common as c
from app.services.reports import sales as sales_report
from app.services.reports import sql

SOURCE_LABELS = {
    "manual": "Created by hand", "bulk": "Bulk batches", "welcome": "Welcome offer", "abandoned_cart": "Cart reminders",
    "campaign": "Email campaigns", "winback": "Win-back", "newsletter": "Newsletter",
}


def sale_status(row: c.Row, now: datetime) -> str:
    if not row["is_active"]:
        return "paused"
    if row["starts_at"] and row["starts_at"] > now:
        return "scheduled"
    if row["ends_at"] and row["ends_at"] <= now:
        return "ended"
    return "live"


def sale_rows(found: list[c.Row], now: datetime) -> list[c.Row]:
    out = []
    for r in found:
        revenue, given = c.num(r["revenue"]), c.num(r["given_away"])
        out.append({
            "id": r["id"], "name": r["name"], "kind": r["kind"], "value": c.num(r["value"]), "status": sale_status(r, now),
            "starts_at": r["starts_at"].isoformat() if r["starts_at"] else None, "ends_at": r["ends_at"].isoformat() if r["ends_at"] else None,
            "units": r["units"], "orders": r["orders"], "revenue": revenue, "given_away": given,
            "avg_discount": c.ratio(given, revenue + given),
        })
    return out


def coupon_rows(found: list[c.Row]) -> list[c.Row]:
    return [
        {
            "coupon_id": r["coupon_id"], "code": r["code"], "source": r["source"], "kind": r["kind"], "orders": r["orders"],
            "discount": c.num(r["discount"]), "revenue": c.num(r["revenue"]), "return_per_dollar": c.avg(c.num(r["revenue"]), c.num(r["discount"])),
        }
        for r in found
    ]


def source_rows(found: list[c.Row]) -> list[c.Row]:
    return [
        {
            "source": r["source"], "label": SOURCE_LABELS.get(r["source"], r["source"]), "issued": r["issued"], "redeemed": r["redeemed"],
            "redemption_rate": c.ratio(r["redeemed"], r["issued"]), "discount": c.num(r["discount"]), "revenue": c.num(r["revenue"]),
        }
        for r in found
    ]


def campaign_rows(found: list[c.Row]) -> list[c.Row]:
    return [
        {
            "id": r["id"], "name": r["name"], "segment": r["segment"], "recipients": r["recipients"], "sent_at": r["sent_at"].isoformat(),
            "coupons": r["coupons"], "redeemed": r["redeemed"], "redemption_rate": c.ratio(r["redeemed"], r["coupons"]),
            "discount": c.num(r["discount"]), "revenue": c.num(r["revenue"]),
        }
        for r in found
    ]


async def cart_numbers(session: AsyncSession, rng: DateRange, now: datetime) -> dict[str, Any]:
    p = c.params(rng, active_cutoff=now - ACTIVE_WINDOW)
    f = await c.one(session, sql.CART_FUNNEL, p)
    rec = await c.one(session, sql.CART_RECOVERY, p)
    settled = f.get("converted", 0) + f.get("abandoned", 0)
    reminded = rec.get("carts_reminded", 0)
    return {
        "started": f.get("started", 0), "converted": f.get("converted", 0), "abandoned": f.get("abandoned", 0),
        "abandoned_value": c.num(f.get("abandoned_value")), "abandonment_rate": c.ratio(f.get("abandoned", 0), settled),
        "reached_checkout": f.get("reached_checkout", 0), "checkout_completed": f.get("checkout_completed", 0),
        "checkout_completion": c.ratio(f.get("checkout_completed", 0), f.get("reached_checkout", 0)),
        "recovery": {
            "carts_reminded": reminded, "reminders_sent": rec.get("reminders_sent", 0), "recovered": rec.get("recovered", 0),
            "recovered_revenue": c.num(rec.get("recovered_revenue")), "recovery_rate": c.ratio(rec.get("recovered", 0), reminded),
        },
    }


async def report(session: AsyncSession, rng: DateRange, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    p = c.params(rng)
    totals = await sales_report.totals(session, rng)
    before = await sales_report.totals(session, rng.previous())
    discounted = totals["discounted_orders"]
    return {
        "range": c.range_info(rng),
        "kpis": [
            c.kpi("discounts", "Discounts given", totals["discounts"], before["discounts"], "money", "Sales, cart offers and coupons together.", "none"),
            c.kpi("discount_rate", "Discount rate", totals["discount_rate"], before["discount_rate"], "percent", "Discounts as a share of item value before discounts.", "none"),
            c.kpi("discount_share", "Orders with a discount", totals["discount_share"], before["discount_share"], "percent",
                  "If most orders use a discount, shoppers start waiting for one.", "none"),
            c.kpi("sale_savings", "Sale price savings", totals["sale_savings"], before["sale_savings"], "money", "How much cheaper sale prices made the items.", "none"),
        ],
        "summary": {
            "discounts": totals["discounts"], "discounted_orders": discounted,
            "avg_discount_per_order": c.avg(totals["discounts"], discounted),
            "split": sales_report.discount_split(await c.rows(session, sql.DISCOUNT_SPLIT, p)),
        },
        "sales": sale_rows(await c.rows(session, sql.SALE_PERFORMANCE, p), now),
        "coupons": coupon_rows(await c.rows(session, sql.COUPON_PERFORMANCE, p)),
        "sources": source_rows(await c.rows(session, sql.COUPON_SOURCES, p)),
        "offers": c.clean_all(await c.rows(session, sql.OFFER_PERFORMANCE, p)),
        "campaigns": campaign_rows(await c.rows(session, sql.CAMPAIGN_PERFORMANCE, p)),
        "carts": await cart_numbers(session, rng, now),
    }
