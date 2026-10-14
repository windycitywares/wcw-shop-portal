"""Improvement suggestions: gather the numbers the rules need, then run `domain.insights`.

The rules themselves are plain functions in `app/domain/insights.py`; this module only collects their inputs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import catalog_health
from app.domain import insights as rules
from app.domain.contacts import SERVICE_ONLY_SOURCES
from app.domain.timeutil import DateRange
from app.services.reports import common as c
from app.services.reports import inventory, products, promotions, sales, sql, traffic


def channel_shares(channels: list[c.Row]) -> dict[str, float]:
    """Each source's share of attributed revenue (orders without a known source are left out)."""
    revenue = {r["channel"]: r["revenue"] for r in channels if r["revenue"] > 0 and r["channel"] not in (None, "unknown")}
    total = sum(revenue.values())
    return {k: v / total for k, v in revenue.items()} if total else {}


async def build_metrics(
    session: AsyncSession, rng: DateRange, *, setup: dict[str, bool], low_threshold: int, free_threshold: Decimal | None, now: datetime | None = None,
    sold: dict[str, Any] | None = None, visits: dict[str, Any] | None = None, product_rows: list[c.Row] | None = None, stock: list[c.Row] | None = None,
) -> dict[str, Any]:
    """`sold`, `visits`, `product_rows` and `stock` can be passed in when the caller already has them (saves repeating the queries)."""
    now = now or datetime.now(timezone.utc)
    p = c.params(rng, service_only=list(SERVICE_ONLY_SOURCES), threshold=free_threshold or Decimal(0))
    sold = sold if sold is not None else await sales.totals(session, rng)
    visits = visits if visits is not None else await traffic.totals(session, rng)
    carts = await promotions.cart_numbers(session, rng, now)
    by_device = {
        (r["label"] or "unknown"): {"sessions": r["sessions"], "orders": r["ordered"]}
        for r in await c.rows(session, sql.FUNNEL_BY.format(col="s.device"), p)
    }
    product_rows = product_rows if product_rows is not None else await products.table(session, rng)
    terms = await c.rows(session, sql.SEARCH_TERMS, p)
    stock = stock if stock is not None else inventory.build_rows(await c.rows(session, sql.STOCK_LEVELS), low_threshold)
    stock_inputs = inventory.insight_inputs(stock, c.clean_all(await c.rows(session, sql.STOCK_WAITLIST)))
    catalog = catalog_health.assess(await c.rows(session, sql.CATALOG_ROWS))
    lifetime_customers = await c.one(session, sql.CUSTOMER_TOTALS)
    consent = await c.one(session, sql.CONSENT, p)
    news = await c.one(session, sql.NEWSLETTER, p)
    requests = await c.one(session, sql.REVIEW_REQUESTS, p)
    near = await c.one(session, sql.NEAR_FREE_SHIPPING, p) if free_threshold else {}
    vitals = {v["name"]: v for v in await c.rows(session, sql.VITALS, p)}
    decisions = consent.get("accepted", 0) + consent.get("declined", 0)
    lcp, cls = vitals.get("LCP"), vitals.get("CLS")
    return {
        "setup": setup,
        "sessions": visits["sessions"], "session_orders": visits["converted"], "conversion_rate": visits["conversion_rate"],
        "carts": {"started": carts["started"], "abandonment_rate": carts["abandonment_rate"], "abandoned_value": carts["abandoned_value"]},
        "checkout": {"started": carts["reached_checkout"], "completed": carts["checkout_completed"]},
        "devices": by_device,
        "viewed_not_bought": products.viewed_not_bought(product_rows),
        "zero_result_searches": [{"q": t["term"], "n": t["no_results"]} for t in terms if t["no_results"] > 0],
        **stock_inputs,
        "catalog_score": catalog["score"], "catalog_issues": catalog["issues"],
        "discount_share": sold["discount_share"], "orders": sold["orders"],
        "free_shipping": (
            {"threshold": float(free_threshold), "near_share": c.ratio(near.get("near", 0), near.get("orders", 0)), "aov": sold["aov"]} if free_threshold else None
        ),
        "refund_rate": sold["refund_rate"],
        "repeat_rate": c.ratio(lifetime_customers.get("repeat_customers", 0), lifetime_customers.get("customers", 0)),
        "customers": lifetime_customers.get("customers", 0),
        "channel_share": channel_shares(traffic.channel_rows(await c.rows(session, sql.TRAFFIC_BY_CHANNEL, p))),
        "pending_reviews": await c.scalar(session, sql.WAITING_REVIEWS) or 0,
        "review_rate": c.ratio(requests.get("reviewed", 0), requests.get("orders", 0)),
        "unshipped_over_2d": await c.scalar(session, sql.UNSHIPPED) or 0,
        "newsletter": {"signups": news.get("joined", 0), "sessions": visits["sessions"]},
        "web_vitals": {"lcp_p75_ms": float(lcp["p75"]) if lcp else None, "cls_p75": float(cls["p75"]) if cls else None},
        "consent_rate": c.ratio(consent.get("accepted", 0), decisions), "consent_decisions": decisions,
    }


async def suggestions(
    session: AsyncSession, rng: DateRange, *, setup: dict[str, bool], low_threshold: int, free_threshold: Decimal | None,
    now: datetime | None = None, limit: int | None = None, **known: Any,
) -> list[dict[str, Any]]:
    metrics = await build_metrics(session, rng, setup=setup, low_threshold=low_threshold, free_threshold=free_threshold, now=now, **known)
    return [i.as_dict() for i in rules.generate(metrics, limit)]
