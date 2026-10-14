"""Visitors: where they come from, what they do, where they drop out, and how fast the pages feel.

Traffic numbers only include visitors who accepted analytics. Orders and revenue elsewhere are complete.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.timeutil import DateRange
from app.services.reports import common as c
from app.services.reports import sql

DIMENSIONS = {"device": "s.device", "browser": "s.browser", "system": "s.os", "language": "s.locale"}
FUNNEL_STEPS = (
    ("sessions", "Visits"), ("viewed", "Viewed a product"), ("carted", "Added to cart"),
    ("checkout", "Started checkout"), ("ordered", "Placed an order"), ("paid", "Paid"),
)
EVENT_LABELS = {
    "page_view": "Page views", "product_view": "Product views", "search": "Searches", "add_to_cart": "Added to cart",
    "remove_from_cart": "Removed from cart", "view_cart": "Opened the cart", "begin_checkout": "Started checkout",
    "wishlist_add": "Saved to wishlist", "newsletter_signup": "Newsletter sign-ups", "coupon_applied": "Coupon applied",
    "coupon_failed": "Coupon rejected", "notify_me": "Asked to be told when back in stock", "client_error": "Page errors",
    "recently_viewed_click": "Clicked a recently viewed item", "recommendation_click": "Clicked a recommendation", "share": "Shared a page",
}
DEPTH_BANDS = {1: "1 page", 2: "2 pages", 3: "3-5 pages", 4: "6 or more pages"}
# Core Web Vitals "good" / "poor" boundaries (web.dev): the 75th percentile should be in the good range.
VITAL_LIMITS = {
    "LCP": (2500, 4000, "ms", "Largest Contentful Paint: how long the main content takes to appear"),
    "INP": (200, 500, "ms", "Interaction to Next Paint: how quickly the page reacts to a tap or click"),
    "CLS": (0.1, 0.25, "", "Cumulative Layout Shift: how much the page jumps around while loading"),
    "FCP": (1800, 3000, "ms", "First Contentful Paint: when anything first appears"),
    "TTFB": (800, 1800, "ms", "Time to First Byte: how fast the server answers"),
}


async def totals(session: AsyncSession, rng: DateRange) -> dict[str, Any]:
    k = await c.one(session, sql.TRAFFIC_KPIS, c.params(rng))
    sessions = k.get("sessions", 0)
    return {
        "sessions": sessions, "visitors": k.get("visitors", 0), "new_sessions": k.get("new_sessions", 0),
        "page_views": k.get("page_views", 0), "bounced": k.get("bounced", 0), "converted": k.get("converted", 0),
        "bounce_rate": c.ratio(k.get("bounced", 0), sessions), "pages_per_session": c.avg(k.get("page_views", 0), sessions),
        "avg_seconds": c.num(k.get("avg_seconds"), 0), "conversion_rate": c.ratio(k.get("converted", 0), sessions),
        "new_visitor_share": c.ratio(k.get("new_sessions", 0), sessions),
    }


def traffic_kpis(now: dict[str, Any], before: dict[str, Any]) -> list[c.Row]:
    return [
        c.kpi("sessions", "Visits", now["sessions"], before["sessions"], "number", "A visit is one stay on the site (it ends after 30 minutes of inactivity)."),
        c.kpi("visitors", "Visitors", now["visitors"], before["visitors"], "number", "Different browsers that visited. The same person on two devices counts twice."),
        c.kpi("page_views", "Page views", now["page_views"], before["page_views"], "number"),
        c.kpi("pages_per_session", "Pages per visit", now["pages_per_session"], before["pages_per_session"], "decimal"),
        c.kpi("bounce_rate", "Bounce rate", now["bounce_rate"], before["bounce_rate"], "percent", "Visits that looked at a single page and left.", "down"),
        c.kpi("avg_seconds", "Time on site", now["avg_seconds"], before["avg_seconds"], "duration", "Average length of visits that looked at more than one page."),
        c.kpi("conversion_rate", "Conversion rate", now["conversion_rate"], before["conversion_rate"], "percent", "Visits that placed an order."),
        c.kpi("new_visitor_share", "New visitors", now["new_visitor_share"], before["new_visitor_share"], "percent", "Visits from a browser we had not seen before.", "none"),
    ]


def with_shares(found: list[c.Row]) -> list[c.Row]:
    total = sum(r["sessions"] for r in found)
    return [
        {"label": r["label"], "sessions": r["sessions"], "share": c.ratio(r["sessions"], total), "bounce_rate": c.ratio(r["bounced"], r["sessions"])}
        for r in found
    ]


def channel_rows(found: list[c.Row]) -> list[c.Row]:
    total = sum(r["sessions"] for r in found)
    out = []
    for r in found:
        conversion = c.ratio(r["orders"], r["sessions"])
        out.append({
            "channel": r["channel"], "sessions": r["sessions"], "visitors": r["visitors"], "share": c.ratio(r["sessions"], total),
            "bounce_rate": c.ratio(r["bounced"], r["sessions"]), "orders": r["orders"], "revenue": c.num(r["revenue"]),
            "conversion": min(conversion, 1.0) if conversion is not None else None,
            "revenue_per_visit": c.avg(c.num(r["revenue"]), r["sessions"]),
        })
    return out


async def report(session: AsyncSession, rng: DateRange) -> dict[str, Any]:
    now = await totals(session, rng)
    before = await totals(session, rng.previous())
    p = c.params(rng)
    consent = await c.one(session, sql.CONSENT, p)
    accepted, declined = consent.get("accepted", 0), consent.get("declined", 0)
    dimensions = {
        name: with_shares(await c.rows(session, sql.TRAFFIC_DIMENSION.format(col=col, limit=8), p)) for name, col in DIMENSIONS.items()
    }
    landing = await c.rows(session, sql.LANDING_PAGES, p)
    campaigns = await c.rows(session, sql.CAMPAIGNS, p)
    return {
        "range": c.range_info(rng),
        "kpis": traffic_kpis(now, before),
        "totals": now,
        "series": c.fill_series(rng, await c.rows(session, sql.TRAFFIC_SERIES, p), {"sessions": 0, "visitors": 0}),
        "channels": channel_rows(await c.rows(session, sql.TRAFFIC_BY_CHANNEL, p)),
        "devices": dimensions["device"], "browsers": dimensions["browser"], "systems": dimensions["system"], "languages": dimensions["language"],
        "landing_pages": [
            {"path": r["path"], "sessions": r["sessions"], "bounce_rate": c.ratio(r["bounced"], r["sessions"]), "conversion": c.ratio(r["converted"], r["sessions"])}
            for r in landing
        ],
        "referrers": c.clean_all(await c.rows(session, sql.REFERRERS, p)),
        "campaigns": [
            {"campaign": r["campaign"], "source": r["source"], "medium": r["medium"], "sessions": r["sessions"], "orders": r["orders"],
             "revenue": c.num(r["revenue"]), "conversion": c.ratio(r["orders"], r["sessions"])}
            for r in campaigns
        ],
        "consent": {"accepted": accepted, "declined": declined, "rate": c.ratio(accepted, accepted + declined)},
        "live_visitors": await c.scalar(session, sql.LIVE_NOW) or 0,
    }


# ---- funnel -----------------------------------------------------------------------------------------


def funnel_steps(row: c.Row) -> list[c.Row]:
    steps: list[c.Row] = []
    first = row.get("sessions", 0)
    previous = None
    for key, label in FUNNEL_STEPS:
        count = int(row.get(key, 0))
        of_prev = None if previous is None else (min(count / previous, 1.0) if previous else None)
        steps.append({
            "key": key, "label": label, "count": count, "of_previous": of_prev,
            "of_total": min(count / first, 1.0) if first else None, "lost": 0 if previous is None else max(previous - count, 0),
        })
        previous = count
    return steps


def biggest_drop(steps: list[c.Row]) -> c.Row | None:
    """The step where the largest share of shoppers leave (ignoring steps with too few people to judge)."""
    candidates = [(s, steps[i]) for i, s in enumerate(steps[1:]) if s["of_previous"] is not None and steps[i]["count"] >= 20]
    if not candidates:
        return None
    step, prev = min(candidates, key=lambda t: t[0]["of_previous"])
    return {"from": prev["label"], "to": step["label"], "lost": step["lost"], "kept": step["of_previous"]}


def funnel_group(rows: list[c.Row]) -> list[c.Row]:
    out = []
    for r in rows:
        total = r["sessions"]
        out.append({
            "label": r["label"] if r["label"] is not None else "(unknown)", "sessions": total,
            "viewed_rate": c.ratio(r["viewed"], total), "cart_rate": c.ratio(r["carted"], total), "checkout_rate": c.ratio(r["checkout"], total),
            "order_rate": c.ratio(r["ordered"], total), "paid_rate": c.ratio(r["paid"], total),
            "steps": funnel_steps(r),
        })
    return out


async def funnel_report(session: AsyncSession, rng: DateRange) -> dict[str, Any]:
    p = c.params(rng)
    steps = funnel_steps(await c.one(session, sql.FUNNEL, p))
    sessions = steps[0]["count"]
    return {
        "range": c.range_info(rng),
        "steps": steps,
        "overall_conversion": c.ratio(steps[-1]["count"], sessions),
        "biggest_drop": biggest_drop(steps),
        "by_device": funnel_group(await c.rows(session, sql.FUNNEL_BY.format(col="s.device"), p)),
        "by_channel": funnel_group(await c.rows(session, sql.FUNNEL_BY.format(col="s.channel"), p)),
        "note": "Each step counts visits that did that thing at least once, so a step can be larger than the one before it when a visitor skipped it (for example, went straight to checkout).",
    }


# ---- behaviour --------------------------------------------------------------------------------------


async def behavior_report(session: AsyncSession, rng: DateRange) -> dict[str, Any]:
    p = c.params(rng)
    terms = await c.rows(session, sql.SEARCH_TERMS, p)
    searches = sum(t["searches"] for t in terms)
    no_results = sum(t["no_results"] for t in terms)
    searchers = await c.one(session, sql.SEARCHERS, p)
    searched, ordered = searchers.get("searched", 0), searchers.get("ordered", 0)
    sessions = await c.scalar(session, "SELECT count(*)::int FROM analytics_sessions s WHERE " + sql.SESSION_RANGE, p) or 0
    others = max(sessions - searched, 0)
    depth = {int(r["band"]): r["sessions"] for r in await c.rows(session, sql.SESSION_DEPTH, p)}
    events = await c.rows(session, sql.EVENT_TOTALS, p)
    return {
        "range": c.range_info(rng),
        "top_pages": c.clean_all(await c.rows(session, sql.TOP_PAGES, p)),
        "events": [{"type": e["type"], "label": EVENT_LABELS.get(e["type"], e["type"].replace("_", " ").capitalize()), "events": e["events"], "sessions": e["sessions"]} for e in events],
        "depth": [{"band": label, "sessions": depth.get(b, 0), "share": c.ratio(depth.get(b, 0), sessions)} for b, label in DEPTH_BANDS.items()],
        "search": {
            "searches": searches, "no_results": no_results, "no_result_rate": c.ratio(no_results, searches),
            "terms": [
                {"term": t["term"], "searches": t["searches"], "avg_results": c.num(t["avg_results"], 1), "no_results": t["no_results"]}
                for t in terms
            ],
            "searchers": searched, "searcher_conversion": c.ratio(searchers.get("searched_and_ordered", 0), searched),
            "other_conversion": c.ratio(max(ordered - searchers.get("searched_and_ordered", 0), 0), others),
        },
    }


def zero_result_terms(report: dict[str, Any], limit: int = 10) -> list[c.Row]:
    """[{q, n}] for the insights: searches that found nothing, most frequent first."""
    rows = [{"q": t["term"], "n": t["no_results"]} for t in report["search"]["terms"] if t["no_results"] > 0]
    return sorted(rows, key=lambda r: (-r["n"], r["q"]))[:limit]


# ---- speed & errors -----------------------------------------------------------------------------------


def vital_rating(name: str, p75: float) -> str:
    good, poor, _, _ = VITAL_LIMITS.get(name, (None, None, "", ""))
    if good is None:
        return "unknown"
    return "good" if p75 <= good else ("poor" if p75 > poor else "needs work")


async def performance_report(session: AsyncSession, rng: DateRange) -> dict[str, Any]:
    p = c.params(rng)
    vitals = [
        {
            "name": v["name"], "samples": v["samples"], "p75": c.num(v["p75"], 3), "median": c.num(v["median"], 3),
            "rating": vital_rating(v["name"], float(v["p75"])), "unit": VITAL_LIMITS.get(v["name"], (0, 0, "", ""))[2],
            "good_under": VITAL_LIMITS.get(v["name"], (None,))[0], "meaning": VITAL_LIMITS.get(v["name"], (0, 0, "", ""))[3],
        }
        for v in await c.rows(session, sql.VITALS, p)
    ]
    by_device: dict[str, dict[str, Any]] = {}
    for r in await c.rows(session, sql.VITALS_BY_DEVICE, p):
        by_device.setdefault(r["device"] or "unknown", {})[r["name"]] = c.num(r["p75"], 3)
    return {
        "range": c.range_info(rng),
        "vitals": vitals,
        "by_device": [{"device": d, "p75": values} for d, values in sorted(by_device.items())],
        "slowest_pages": [{"path": r["path"], "samples": r["samples"], "lcp_p75": c.num(r["p75"], 0)} for r in await c.rows(session, sql.SLOWEST_PAGES, p)],
        "errors": c.clean_all(await c.rows(session, sql.CLIENT_ERRORS, p)),
        "note": "Measured in real visitors' browsers (only those who accepted analytics). The 75th percentile means three out of four visits were at least this fast.",
    }
