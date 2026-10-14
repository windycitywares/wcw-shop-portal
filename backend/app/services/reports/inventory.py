"""Inventory and catalog health: what to reorder, what is stuck on the shelf, and which listings need work."""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import catalog_health
from app.services.reports import common as c
from app.services.reports import sql

LOW_DAYS = 14  # fewer days of cover than this counts as low
COVER_DAYS = 45  # suggested reorder quantity covers this many days of selling
DEAD_DAYS = 90  # nothing sold for this long = dead stock


def stock_status(stock: int | None, stock_status_: str, sold_30d: int, sold_90d: int, low_threshold: int) -> tuple[str, float | None]:
    """(status, days of cover). Status: out | low | dead | healthy | untracked."""
    rate = sold_30d / 30 if sold_30d > 0 else sold_90d / 90
    if stock is None:
        return ("out" if stock_status_ == "out_of_stock" else "untracked"), None
    days = None if rate <= 0 else stock / rate
    if stock <= 0 or stock_status_ == "out_of_stock":
        return "out", 0.0
    if stock <= low_threshold or (days is not None and days < LOW_DAYS):
        return "low", days
    if sold_90d == 0:
        return "dead", days
    return "healthy", days


def display_title(product: str, variant: str | None) -> str:
    """'Oak Urn' + 'Oak Urn - Large' -> 'Oak Urn - Large'; 'Oak Urn' + 'Large' -> 'Oak Urn (Large)'."""
    if not variant or variant == product:
        return product
    return variant if variant.lower().startswith(product.lower()) else f"{product} ({variant})"


def build_rows(found: list[c.Row], low_threshold: int) -> list[c.Row]:
    rows = []
    for r in found:
        stock = r["stock"]
        status, days = stock_status(stock, r["stock_status"], r["sold_30d"], r["sold_90d"], low_threshold)
        rate = r["sold_30d"] / 30 if r["sold_30d"] > 0 else r["sold_90d"] / 90
        price, cost = c.num(r["base_price"]) if r["base_price"] is not None else None, c.num(r["cost_price"]) if r["cost_price"] is not None else None
        title = display_title(r["title"], r["variant"])
        rows.append({
            "id": r["id"], "title": title, "product_title": r["title"], "slug": r["slug"], "sku": r["sku"], "stock": stock, "status": status,
            "sold_30d": r["sold_30d"], "sold_90d": r["sold_90d"], "days_of_cover": round(days, 1) if days is not None else None,
            "waiting": r["waiting"], "price": price, "cost": cost,
            "value_at_cost": round(stock * cost, 2) if stock and cost is not None else None,
            "value_at_retail": round(stock * price, 2) if stock and price is not None else None,
            "reorder": max(0, math.ceil(rate * COVER_DAYS) - stock) if stock is not None and rate > 0 and status in ("low", "out") else 0,
        })
    return rows


def summary(rows: list[c.Row]) -> dict[str, Any]:
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("out", "low", "dead", "healthy", "untracked")}
    tracked = [r for r in rows if r["stock"] is not None]
    return {
        "items": len(rows), "tracked": len(tracked), **counts,
        "units": sum(r["stock"] for r in tracked if r["stock"] and r["stock"] > 0),
        "value_at_cost": round(sum(r["value_at_cost"] or 0 for r in rows), 2),
        "value_at_retail": round(sum(r["value_at_retail"] or 0 for r in rows), 2),
        "costed_items": sum(1 for r in tracked if r["cost"] is not None and (r["stock"] or 0) > 0),
        "waiting": sum(r["waiting"] for r in rows),
    }


def insight_inputs(rows: list[c.Row], waitlist: list[c.Row]) -> dict[str, Any]:
    """The pieces the recommendation rules read: low stock, dead stock, and demand for out-of-stock items."""
    low = [r for r in rows if r["status"] == "low"]
    dead = [r for r in rows if r["status"] == "dead"]
    return {
        "low_stock": [{"title": r["title"], "stock": r["stock"], "sold_30d": r["sold_30d"]} for r in sorted(low, key=lambda r: (-r["sold_30d"], r["id"]))],
        "dead_stock": {"count": len(dead), "value": round(sum(r["value_at_cost"] or 0 for r in dead), 2) or None},
        "stockout_demand": [{"title": w["title"], "requests": w["requests"]} for w in waitlist],
    }


async def inventory_report(session: AsyncSession, low_threshold: int) -> dict[str, Any]:
    rows = build_rows(await c.rows(session, sql.STOCK_LEVELS), low_threshold)
    waitlist = c.clean_all(await c.rows(session, sql.STOCK_WAITLIST))
    order = {"out": 0, "low": 1, "dead": 2, "healthy": 3, "untracked": 4}
    rows.sort(key=lambda r: (order[r["status"]], r["days_of_cover"] if r["days_of_cover"] is not None else 1e9, r["id"]))
    return {
        "summary": summary(rows),
        "items": rows[:500],
        "waitlist": waitlist,
        "rules": {
            "low": f"At or below the low-stock level ({low_threshold}) or fewer than {LOW_DAYS} days of cover at the recent selling pace.",
            "dead": f"In stock but nothing sold in {DEAD_DAYS} days.",
            "reorder": f"Units needed to cover about {COVER_DAYS} days at the recent selling pace.",
        },
    }


async def catalog_report(session: AsyncSession) -> dict[str, Any]:
    return catalog_health.assess(await c.rows(session, sql.CATALOG_ROWS))
