"""Products: what sells, what gets looked at but not bought, what is bought together, and what customers say."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.timeutil import DateRange
from app.services.reports import common as c
from app.services.reports import sql

MIN_VIEWERS = 10  # a product needs this many viewers before "no sales" means anything
ABC_A, ABC_B = 0.80, 0.95  # classes A/B/C cover the best-selling 80% / next 15% / last 5% of revenue


def abc_classes(rows: list[c.Row]) -> dict[int, str]:
    """A = the products that earn 80% of merchandise revenue, B = the next 15%, C = the rest. Unsold products get no class."""
    sold = sorted((r for r in rows if c.num(r["merchandise"]) > 0), key=lambda r: (-c.num(r["merchandise"]), r["id"]))
    total = sum(c.num(r["merchandise"]) for r in sold)
    classes: dict[int, str] = {}
    running = 0.0
    for r in sold:
        share_before = running / total if total else 1.0
        classes[r["id"]] = "A" if share_before < ABC_A else ("B" if share_before < ABC_B else "C")
        running += c.num(r["merchandise"])
    return classes


def derive(row: c.Row, total_merchandise: float, classes: dict[int, str]) -> c.Row:
    merchandise = c.num(row["merchandise"])
    viewers, carted, bought = row["viewers"], row["carted"], row["bought_sessions"]
    conversion = c.ratio(bought, viewers)
    cart_to_buy = c.ratio(bought, carted)
    return {
        "id": row["id"], "title": row["title"], "slug": row["slug"], "sku": row["sku"], "stock_status": row["stock_status"],
        "price": c.num(row["base_price"]) if row["base_price"] is not None else None,
        "stock": row["stock"], "rating": c.num(row["rating_avg"]) if row["rating_count"] else None, "rating_count": row["rating_count"],
        "units": row["units"], "orders": row["orders"], "merchandise": merchandise,
        "profit": c.num(row["profit"]) if row["profit"] is not None else None,
        "margin": c.ratio(row["profit"], merchandise) if row["profit"] is not None else None,
        "returned": row["returned"], "return_rate": c.ratio(row["returned"], row["units"]),
        "views": row["views"], "viewers": viewers, "carted": carted, "wishlist_adds": row["wishlist_adds"],
        "view_to_cart": c.ratio(carted, viewers),
        "conversion": min(conversion, 1.0) if conversion is not None else None,  # visitors who decline analytics can still buy
        "cart_to_buy": min(cart_to_buy, 1.0) if cart_to_buy is not None else None,
        "revenue_share": c.ratio(merchandise, total_merchandise),
        "abc": classes.get(row["id"]),
    }


def viewed_not_bought(products: list[c.Row], limit: int = 8) -> list[c.Row]:
    found = [p for p in products if p["units"] == 0 and p["viewers"] >= MIN_VIEWERS]
    found.sort(key=lambda p: (-p["views"], p["id"]))
    return [{"id": p["id"], "title": p["title"], "slug": p["slug"], "views": p["views"], "viewers": p["viewers"], "carted": p["carted"]} for p in found[:limit]]


def abc_summary(products: list[c.Row]) -> dict[str, Any]:
    total = sum(p["merchandise"] for p in products)
    out: dict[str, Any] = {}
    for key in ("A", "B", "C"):
        group = [p for p in products if p["abc"] == key]
        out[key] = {"count": len(group), "revenue": round(sum(p["merchandise"] for p in group), 2), "share": c.ratio(sum(p["merchandise"] for p in group), total)}
    out["unsold"] = {"count": sum(1 for p in products if p["abc"] is None), "revenue": 0.0, "share": None}
    return out


async def review_stats(session: AsyncSession, rng: DateRange) -> dict[str, Any]:
    p = c.params(rng)
    summary = await c.one(session, sql.REVIEW_SUMMARY, p)
    distribution = {int(r["rating"]): int(r["n"]) for r in await c.rows(session, sql.REVIEW_DISTRIBUTION)}
    requests = await c.one(session, sql.REVIEW_REQUESTS, p)
    return {
        "approved": summary.get("approved", 0), "pending": summary.get("pending", 0), "rejected": summary.get("rejected", 0),
        "average": c.num(summary.get("average")) if summary.get("approved") else None,
        "answered": summary.get("answered", 0), "critical": summary.get("critical", 0),
        "critical_unanswered": summary.get("critical_unanswered", 0), "new_in_range": summary.get("new_in_range", 0),
        "distribution": [{"rating": n, "count": distribution.get(n, 0)} for n in (5, 4, 3, 2, 1)],
        "lowest_rated": c.clean_all(await c.rows(session, sql.LOWEST_RATED)),
        "requests": {
            "orders": requests.get("orders", 0), "requested": requests.get("requested", 0), "reviewed": requests.get("reviewed", 0),
            "review_rate": c.ratio(requests.get("reviewed", 0), requests.get("orders", 0)),
        },
    }


async def table(session: AsyncSession, rng: DateRange) -> list[c.Row]:
    """Every published product with its sales, attention and ABC class for the period."""
    raw = await c.rows(session, sql.PRODUCT_TABLE, c.params(rng))
    total = sum(c.num(r["merchandise"]) for r in raw)
    classes = abc_classes(raw)
    return [derive(r, total, classes) for r in raw]


async def report(session: AsyncSession, rng: DateRange) -> dict[str, Any]:
    products = await table(session, rng)
    total = sum(p["merchandise"] for p in products)
    return {
        "range": c.range_info(rng),
        "summary": {
            "products": len(products), "sold": sum(1 for p in products if p["units"] > 0), "units": sum(p["units"] for p in products),
            "merchandise": round(total, 2), "views": sum(p["views"] for p in products), "wishlist_adds": sum(p["wishlist_adds"] for p in products),
            "abc": abc_summary(products),
        },
        "products": products[:300],
        "viewed_not_bought": viewed_not_bought(products),
        "bought_together": c.clean_all(await c.rows(session, sql.BOUGHT_TOGETHER)),
        "reviews": await review_stats(session, rng),
    }
