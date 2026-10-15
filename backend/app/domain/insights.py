"""Rule-based recommendations: turn the numbers on the reports into "here is what to do next".

Each rule looks at a dict of metrics (built by `services/insights.py` from the report queries) and returns
an `Insight` or nothing. Rules never invent data: when a metric is missing or the sample is too small to
mean anything, the rule stays quiet. Thresholds are industry rules of thumb for small online shops and
are collected at the top so they are easy to tune.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

SEVERITY_ORDER = {"critical": 0, "warning": 1, "opportunity": 2, "info": 3, "success": 4}

# Minimum sample sizes before a rate is trusted.
MIN_SESSIONS = 150
MIN_CARTS = 10
MIN_CHECKOUTS = 8
MIN_ORDERS = 10

# Thresholds
LOW_CONVERSION = 0.010  # sessions -> orders
CART_ABANDONMENT_HIGH = 0.75
CHECKOUT_COMPLETION_LOW = 0.45
MOBILE_GAP = 0.5  # mobile converts at less than half of desktop
DISCOUNT_SHARE_HIGH = 0.45
REFUND_RATE_HIGH = 0.06
REPEAT_RATE_LOW = 0.08
REVIEW_RATE_LOW = 0.05
CATALOG_SCORE_LOW = 80
LCP_SLOW_MS = 2500
CLS_BAD = 0.1
CHANNEL_CONCENTRATION = 0.7
CONSENT_LOW = 0.4
NEWSLETTER_RATE_LOW = 0.01


@dataclass
class Insight:
    key: str
    severity: str  # critical | warning | opportunity | info | success
    title: str
    detail: str
    action: str | None = None  # what to do, as a short imperative
    href: str | None = None  # admin page where it can be done
    metrics: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


Metrics = dict[str, Any]
Rule = Callable[[Metrics], "Insight | None"]


def _pct(x: float, digits: int = 0) -> str:
    return f"{x * 100:.{digits}f}%"


def _money(x: float) -> str:
    return f"${x:,.0f}" if abs(x) >= 100 else f"${x:,.2f}"


def _get(m: Metrics, *path: str) -> Any:
    cur: Any = m
    for key in path:
        if not isinstance(cur, dict) or key not in cur or cur[key] is None:
            return None
        cur = cur[key]
    return cur


# --------------------------------------------------------------------------------------------- setup
def setup_gaps(m: Metrics) -> Insight | None:
    setup = _get(m, "setup")
    if not isinstance(setup, dict):
        return None
    labels = {
        "payments_live": "take card payments (add the Stripe keys)",
        "shipping_configured": "set your shipping rates",
        "tax_configured": "set your Illinois sales-tax rate",
        "email_configured": "connect outgoing email",
        "captcha_configured": "turn on the bot check (Turnstile)",
        "welcome_offer": "switch on the welcome offer for new subscribers",
    }
    missing = [text for key, text in labels.items() if key in setup and not setup[key]]
    if not missing:
        return None
    critical = not setup.get("payments_live", True) or not setup.get("email_configured", True)
    return Insight(
        "setup_gaps", "critical" if critical else "warning",
        f"{len(missing)} setup step{'s' if len(missing) != 1 else ''} left before you can sell with confidence",
        "Still to do: " + "; ".join(missing) + ".",
        "Open Settings and finish the checklist", "/admin/settings", {"missing": missing},
    )


# --------------------------------------------------------------------------------------------- funnel
def low_conversion(m: Metrics) -> Insight | None:
    sessions, orders = _get(m, "sessions"), _get(m, "session_orders")
    rate = _get(m, "conversion_rate")
    if rate is None or not sessions or sessions < MIN_SESSIONS or rate >= LOW_CONVERSION:
        return None
    return Insight(
        "low_conversion", "warning", f"Conversion is {_pct(rate, 2)}: under 1 in 100 visits ends in an order",
        f"Out of {sessions:,} visits that accepted analytics, {orders or 0:,} ended in an order. Healthy small shops usually see 1-3%. "
        "Check the funnel to see where visitors drop off before changing prices.",
        "Open the funnel report", "/admin/analytics/funnel", {"conversion_rate": rate, "sessions": sessions},
    )


def high_cart_abandonment(m: Metrics) -> Insight | None:
    carts = _get(m, "carts", "started")
    rate = _get(m, "carts", "abandonment_rate")
    value = _get(m, "carts", "abandoned_value") or 0
    if rate is None or not carts or carts < MIN_CARTS or rate < CART_ABANDONMENT_HIGH:
        return None
    return Insight(
        "cart_abandonment", "opportunity", f"{_pct(rate)} of carts are abandoned ({_money(value)} left behind)",
        "Most carts never become orders, which is normal (the average online shop sees about 70%), but every recovered cart is almost free revenue. "
        "A single gentle reminder email a day later usually wins back 5-10%. For a sensitive purchase like an urn, keep the tone caring and the offer modest.",
        "Review abandoned carts and reminder settings", "/admin/carts", {"abandonment_rate": rate, "value": value},
    )


def checkout_drop(m: Metrics) -> Insight | None:
    started, completed = _get(m, "checkout", "started"), _get(m, "checkout", "completed")
    if not started or started < MIN_CHECKOUTS or completed is None:
        return None
    rate = completed / started
    if rate >= CHECKOUT_COMPLETION_LOW:
        return None
    return Insight(
        "checkout_drop", "warning", f"Only {_pct(rate)} of shoppers who start checkout finish it",
        f"{started - completed} of {started} people reached checkout and left. Typical causes: surprise shipping cost or tax, forced account creation, "
        "too many form fields, or a payment problem. Look at shipping cost against the free-shipping threshold first.",
        "Check shipping and payment settings", "/admin/settings", {"started": started, "completed": completed},
    )


def mobile_gap(m: Metrics) -> Insight | None:
    mobile, desktop = _get(m, "devices", "mobile"), _get(m, "devices", "desktop")
    if not mobile or not desktop:
        return None
    if mobile.get("sessions", 0) < MIN_SESSIONS / 2 or desktop.get("sessions", 0) < MIN_SESSIONS / 2:
        return None
    m_rate = mobile.get("orders", 0) / mobile["sessions"]
    d_rate = desktop.get("orders", 0) / desktop["sessions"]
    if d_rate <= 0 or m_rate >= d_rate * MOBILE_GAP:
        return None
    return Insight(
        "mobile_gap", "warning", f"Mobile converts at {_pct(m_rate, 2)} versus {_pct(d_rate, 2)} on desktop",
        f"{mobile['sessions']:,} mobile visits is a large share of traffic. Walk through the whole purchase on a phone: product photos, size selection, "
        "the cart drawer, address entry and payment. Fixing one blocking step on mobile usually lifts the whole store.",
        "Open traffic by device", "/admin/analytics/traffic", {"mobile_rate": m_rate, "desktop_rate": d_rate},
    )


def high_view_no_sale(m: Metrics) -> Insight | None:
    rows = _get(m, "viewed_not_bought")
    if not rows:
        return None
    top = rows[:3]
    names = ", ".join(f"{r['title']} ({r['views']} views)" for r in top)
    return Insight(
        "viewed_not_bought", "opportunity", f"{len(rows)} product{'s get' if len(rows) != 1 else ' gets'} views but no sales",
        f"{names}. People like them enough to look, then leave. Check price against similar items, photo quality, description clarity "
        "(dimensions, capacity, materials) and shipping time. A small sale or a better first photo is a cheap test.",
        "Review these products", "/admin/analytics/products", {"products": top},
    )


def zero_result_searches(m: Metrics) -> Insight | None:
    rows = _get(m, "zero_result_searches")
    if not rows:
        return None
    total = sum(r["n"] for r in rows)
    if total < 3:
        return None
    terms = ", ".join(f"“{r['q']}” ({r['n']})" for r in rows[:5])
    return Insight(
        "zero_results", "opportunity", f"{total} searches found nothing",
        f"Top missing terms: {terms}. Each is a shopper telling you what they want. Add tags or titles that use their words, "
        "or consider stocking what they ask for.",
        "See search terms", "/admin/analytics/behavior", {"terms": rows[:10]},
    )


# --------------------------------------------------------------------------------------------- catalog & stock
def low_stock(m: Metrics) -> Insight | None:
    rows = _get(m, "low_stock")
    if not rows:
        return None
    selling = [r for r in rows if r.get("sold_30d", 0) > 0] or rows
    names = ", ".join(f"{r['title']} ({r['stock']} left)" for r in selling[:4])
    return Insight(
        "low_stock", "warning", f"{len(rows)} product{'s' if len(rows) != 1 else ''} nearly out of stock",
        f"{names}. Running out of a best seller costs more than the price of the item: the shopper leaves and often doesn't come back.",
        "Plan a restock", "/admin/analytics/inventory", {"products": rows[:10]},
    )


def stockout_demand(m: Metrics) -> Insight | None:
    rows = _get(m, "stockout_demand")
    if not rows:
        return None
    names = ", ".join(f"{r['title']} ({r['requests']} waiting)" for r in rows[:4])
    return Insight(
        "stockout_demand", "opportunity", "Customers are waiting for out-of-stock products",
        f"{names}. These shoppers asked to be emailed when the item returns, so restocking converts almost immediately.",
        "Restock or update availability", "/admin/analytics/inventory", {"products": rows[:10]},
    )


def dead_stock(m: Metrics) -> Insight | None:
    info = _get(m, "dead_stock")
    if not info or info.get("count", 0) < 3:
        return None
    value = info.get("value")
    extra = f" tying up about {_money(value)} at cost" if value else ""
    return Insight(
        "dead_stock", "opportunity", f"{info['count']} products haven't sold in 90 days{extra}",
        "Slow movers still need photos, space and attention. Try a time-boxed sale, bundle them with a best seller, or retire the listing.",
        "Create a clearance sale", "/admin/promotions?tab=sales", {"count": info["count"], "value": value},
    )


def catalog_health(m: Metrics) -> Insight | None:
    score, issues = _get(m, "catalog_score"), _get(m, "catalog_issues") or {}
    if score is None or score >= CATALOG_SCORE_LOW:
        return None
    worst = sorted(issues.items(), key=lambda kv: -kv[1])[:3]
    detail = ", ".join(f"{n} {label}" for label, n in worst if n)
    return Insight(
        "catalog_health", "opportunity", f"Catalog health is {score}/100",
        f"Gaps hurt search ranking and conversion: {detail}. Complete listings convert noticeably better.",
        "Fix the listings", "/admin/analytics/catalog", {"score": score, "issues": issues},
    )


# --------------------------------------------------------------------------------------------- money
def discount_dependency(m: Metrics) -> Insight | None:
    share, orders = _get(m, "discount_share"), _get(m, "orders")
    if share is None or not orders or orders < MIN_ORDERS or share < DISCOUNT_SHARE_HIGH:
        return None
    return Insight(
        "discount_dependency", "warning", f"{_pct(share)} of orders used a discount",
        "When most customers wait for a code, full price stops being the real price and margin erodes. Make offers rarer and more specific "
        "(first order, a bundle, a slow-moving product) instead of store-wide.",
        "Review promotions", "/admin/analytics/promotions", {"discount_share": share},
    )


def free_shipping_nudge(m: Metrics) -> Insight | None:
    threshold = _get(m, "free_shipping", "threshold")
    near = _get(m, "free_shipping", "near_share")
    aov = _get(m, "free_shipping", "aov")
    if not threshold or near is None or near < 0.2:
        return None
    return Insight(
        "free_shipping_nudge", "opportunity", f"{_pct(near)} of orders land just under the {_money(threshold)} free-shipping line",
        f"Average order value is {_money(aov or 0)}. A cart-page progress bar and a low-priced add-on (a keepsake, a candle) "
        "typically move these shoppers over the line and raise order value.",
        "Add a recommended add-on or adjust the threshold", "/admin/settings", {"threshold": threshold, "near_share": near},
    )


def refund_rate(m: Metrics) -> Insight | None:
    rate, orders = _get(m, "refund_rate"), _get(m, "orders")
    if rate is None or not orders or orders < MIN_ORDERS or rate < REFUND_RATE_HIGH:
        return None
    return Insight(
        "refund_rate", "warning", f"{_pct(rate, 1)} of revenue was refunded",
        "Check which products are returned and the reasons given. Wrong-size purchases are the usual cause for urns: "
        "a clear capacity guide (cubic inches per pound of body weight) on every product page prevents most of them.",
        "See refunds by product", "/admin/orders?payment=refunded", {"refund_rate": rate},
    )


def repeat_rate(m: Metrics) -> Insight | None:
    rate, customers = _get(m, "repeat_rate"), _get(m, "customers")
    if rate is None or not customers or customers < 30 or rate >= REPEAT_RATE_LOW:
        return None
    return Insight(
        "repeat_rate", "info", f"{_pct(rate)} of customers have bought more than once",
        "For memorial products that is expected: most customers need one. Growth here comes from new customers and referrals "
        "(funeral homes, veterinarians, cremation services), matching keepsakes and companion urns, rather than win-back discounts.",
        "Explore customers", "/admin/analytics/customers", {"repeat_rate": rate},
    )


def channel_concentration(m: Metrics) -> Insight | None:
    shares = _get(m, "channel_share")
    orders = _get(m, "orders")
    if not shares or not orders or orders < MIN_ORDERS:
        return None
    channel, share = max(shares.items(), key=lambda kv: kv[1])
    if share < CHANNEL_CONCENTRATION:
        return None
    label = channel.replace("_", " ")
    return Insight(
        "channel_concentration", "info", f"{_pct(share)} of attributed revenue comes from {label}",
        "Relying on one source is risky: an algorithm or policy change can cut your sales overnight. Add a second reliable source "
        "(email, search, partnerships).",
        "Open traffic report", "/admin/analytics/traffic", {"channel": channel, "share": share},
    )


# --------------------------------------------------------------------------------------------- engagement
def pending_reviews(m: Metrics) -> Insight | None:
    n = _get(m, "pending_reviews")
    if not n:
        return None
    return Insight(
        "pending_reviews", "info", f"{n} review{'s' if n != 1 else ''} waiting for approval",
        "Reviews are shown only after you approve them. Publishing and answering them promptly builds trust (and a short reply to a critical review often matters more than the review).",
        "Moderate reviews", "/admin/reviews?status=pending", {"count": n},
    )


def review_rate(m: Metrics) -> Insight | None:
    rate, orders = _get(m, "review_rate"), _get(m, "orders")
    if rate is None or not orders or orders < 20 or rate >= REVIEW_RATE_LOW:
        return None
    return Insight(
        "review_rate", "opportunity", f"Only {_pct(rate, 1)} of orders led to a review",
        "Products with reviews convert far better than those without. The automatic review request is sent after delivery; "
        "check that it is enabled and consider a personal thank-you note in the package.",
        "Check the review email settings", "/admin/settings", {"review_rate": rate},
    )


def unshipped_orders(m: Metrics) -> Insight | None:
    n = _get(m, "unshipped_over_2d")
    if not n:
        return None
    return Insight(
        "unshipped_orders", "critical" if n >= 3 else "warning", f"{n} paid order{'s' if n != 1 else ''} not shipped for 2+ days",
        "Late shipping is the top driver of bad reviews and support messages. Ship or send the customer an update today.",
        "Open unfulfilled orders", "/admin/orders?status=paid", {"count": n},
    )


def newsletter_capture(m: Metrics) -> Insight | None:
    signups, sessions = _get(m, "newsletter", "signups"), _get(m, "newsletter", "sessions")
    if signups is None or not sessions or sessions < 300 or signups / sessions >= NEWSLETTER_RATE_LOW:
        return None
    return Insight(
        "newsletter_capture", "opportunity", f"Only {signups} email signups from {sessions:,} visits",
        "A welcome offer on the signup form usually doubles the signup rate. Make sure the welcome offer is enabled and visible.",
        "Check the welcome offer", "/admin/settings", {"signups": signups, "sessions": sessions},
    )


# --------------------------------------------------------------------------------------------- speed & data quality
def slow_pages(m: Metrics) -> Insight | None:
    lcp, cls = _get(m, "web_vitals", "lcp_p75_ms"), _get(m, "web_vitals", "cls_p75")
    if lcp is not None and lcp > LCP_SLOW_MS:
        return Insight(
            "slow_lcp", "warning", f"Pages take {lcp / 1000:.1f}s to show their main content (target: under 2.5s)",
            "Slow pages lose visitors before they see a product, especially on phones. Usual culprits are oversized photos and heavy third-party scripts.",
            "See page speed", "/admin/analytics/performance", {"lcp_p75_ms": lcp},
        )
    if cls is not None and cls > CLS_BAD:
        return Insight(
            "layout_shift", "warning", f"Pages jump around while loading (layout shift {cls:.2f}, target under 0.1)",
            "Content that moves while a shopper is about to tap causes mis-clicks. Reserve space for images and banners.",
            "See page speed", "/admin/analytics/performance", {"cls_p75": cls},
        )
    return None


def low_consent(m: Metrics) -> Insight | None:
    rate, decisions = _get(m, "consent_rate"), _get(m, "consent_decisions")
    if rate is None or not decisions or decisions < 50 or rate >= CONSENT_LOW:
        return None
    return Insight(
        "low_consent", "info", f"Only {_pct(rate)} of visitors accept analytics",
        "Traffic and funnel numbers only include visitors who accepted, so real traffic is higher than shown. Order and revenue numbers are complete. "
        "Plain wording on the banner about what is (and isn't) collected helps.",
        "Review the banner wording", "/admin/settings", {"consent_rate": rate},
    )


def healthy_store(m: Metrics) -> Insight | None:
    rate, sessions = _get(m, "conversion_rate"), _get(m, "sessions")
    if rate is not None and sessions and sessions >= MIN_SESSIONS and rate >= 0.02:
        return Insight(
            "healthy_conversion", "success", f"Conversion of {_pct(rate, 1)} is strong",
            "More than 2 in 100 visits end in an order, well above the typical 1-3% range for small shops. Protect it: avoid big layout changes without testing.",
            None, None, {"conversion_rate": rate},
        )
    return None


RULES: list[Rule] = [
    setup_gaps, unshipped_orders, checkout_drop, low_conversion, mobile_gap, high_cart_abandonment, low_stock,
    refund_rate, discount_dependency, slow_pages, stockout_demand, free_shipping_nudge, zero_result_searches,
    high_view_no_sale, dead_stock, catalog_health, review_rate, newsletter_capture, channel_concentration,
    pending_reviews, repeat_rate, low_consent, healthy_store,
]


def generate(metrics: Metrics, limit: int | None = None) -> list[Insight]:
    """All insights that apply, most urgent first (stable within a severity)."""
    found: list[Insight] = []
    for rule in RULES:
        try:
            insight = rule(metrics)
        except (KeyError, TypeError, ZeroDivisionError, ValueError):  # bad/missing metric: skip the rule, never the report
            insight = None
        if insight is not None:
            found.append(insight)
    found.sort(key=lambda i: SEVERITY_ORDER.get(i.severity, 9))
    return found[:limit] if limit else found
