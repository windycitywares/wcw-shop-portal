"""Fake shop history so the admin reports have something to show (development, browser tests, screenshots).

    python -m app.scripts.demo_data          # add (or refresh) about 4 months of demo orders, visits and reviews
    python -m app.scripts.demo_data --remove  # take it all out again

Everything it creates is recognisable (emails end in @demo.example, order numbers start with DEMO-, SKUs with
DEMO-) so it can be removed cleanly. It refuses to run when ENVIRONMENT=production.

`build()` is plain Python with no database access, so the report queries can be tested against its output.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import random
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

BASE_ID = 900_000
DEMO_EMAIL = "@demo.example"
Rows = dict[str, list[dict[str, Any]]]

FIRST = ["Ana", "Ben", "Carla", "Dev", "Elena", "Frank", "Grace", "Hugo", "Iris", "Jon", "Kira", "Leo", "Maya", "Noah", "Olga", "Pete",
         "Quinn", "Rosa", "Sam", "Tina", "Uma", "Vic", "Wendy", "Xavi", "Yara", "Zed"]
LAST = ["Alvarez", "Brooks", "Chen", "Dawson", "Evans", "Foster", "Garcia", "Hughes", "Ingram", "Jones", "Kim", "Lopez", "Moore", "Nolan",
        "Ortiz", "Patel", "Reyes", "Smith", "Turner", "Vega", "Walker", "Young"]
STATES = [("IL", 30), ("IN", 8), ("WI", 7), ("MI", 7), ("OH", 6), ("TX", 8), ("CA", 8), ("FL", 6), ("NY", 6), ("PA", 4), ("MN", 4), ("GA", 3), ("WA", 3)]
CITIES = {"IL": "Chicago", "IN": "Indianapolis", "WI": "Madison", "MI": "Detroit", "OH": "Columbus", "TX": "Austin", "CA": "San Diego",
          "FL": "Tampa", "NY": "Albany", "PA": "Pittsburgh", "MN": "Duluth", "GA": "Atlanta", "WA": "Tacoma"}
CHANNELS = [("direct", 30), ("organic_search", 25), ("social", 14), ("email", 10), ("marketplace", 9), ("referral", 7), ("paid_search", 5)]
DEVICES = [("mobile", 54), ("desktop", 41), ("tablet", 5)]
BROWSERS = [("Chrome", 55), ("Safari", 30), ("Edge", 8), ("Firefox", 7)]
OSES = {"mobile": [("iOS", 60), ("Android", 40)], "tablet": [("iOS", 70), ("Android", 30)], "desktop": [("Windows", 55), ("macOS", 40), ("Linux", 5)]}
REFERRERS = {"organic_search": ["google.com", "bing.com", "duckduckgo.com"], "social": ["facebook.com", "pinterest.com", "instagram.com"],
             "marketplace": ["etsy.com"], "referral": ["chicago-makers.example", "gift-guide.example", "antiques-forum.example"],
             "paid_search": ["google.com"], "email": [None], "direct": [None]}
SEARCHES = [("walnut bowl", 6), ("candle", 8), ("vintage", 5), ("gift set", 6), ("wall art", 3), ("brass", 3), ("ceramic mug", 4), ("cutting board", 4),
            ("quilt", 3), ("stained glass", 2), ("record player", 2), ("tapestry", 2), ("planter", 3)]
ZERO_RESULT_TERMS = {"quilt", "stained glass", "record player", "tapestry"}

# (title, leaf category, price, variants [(label, price)], cost ratio or None, stock or None, popularity)
CATALOG = [
    ("Hand-Turned Walnut Bowl", "Woodwork", 89, [("Small", 69), ("Large", 89)], 0.42, 14, 10),
    ("Maple Serving Board", "Woodwork", 59, [], 0.45, 9, 7),
    ("Carved Oak Keepsake Box", "Woodwork", 119, [("Standard", 119), ("Engraved", 139)], 0.5, 6, 5),
    ("Live-Edge Wall Shelf", "Woodwork", 149, [], 0.48, 3, 3),
    ("Stoneware Coffee Mug", "Ceramics", 28, [("Speckled", 28)], None, 20, 6),
    ("Glazed Ceramic Planter", "Ceramics", 46, [], 0.4, 11, 4),
    ("Hand-Thrown Vase", "Ceramics", 64, [], 0.5, 4, 2),
    ("Vintage Brass Candlesticks", "Vintage Finds", 79, [("Pair", 79)], 0.46, 2, 2),
    ("Mid-Century Table Lamp", "Vintage Finds", 159, [], 0.35, 4, 6),
    ("Antique Pocket Watch", "Vintage Finds", 189, [], 0.33, 2, 4),
    ("Victorian Pressed-Glass Dish", "Vintage Finds", 39, [], 0.3, 0, 5),
    ("Chicago Skyline Print", "Wall Art", 35, [("8x10", 35), ("11x14", 49)], None, 18, 9),
    ("Botanical Linen Wall Hanging", "Wall Art", 59, [("Small", 59), ("Medium", 69), ("Large", 89)], 0.38, 30, 8),
    ("Framed Pressed Flowers", "Wall Art", 79, [], 0.4, 12, 6),
    ("Macrame Plant Hanger", "Wall Art", 32, [], 0.37, 16, 7),
    ("Hammered Copper Tray", "Vintage Finds", 69, [], None, 8, 3),
    ("Soy Candle Trio", "Candles", 34, [], 0.4, 70, 12),
    ("Beeswax Taper Set", "Candles", 22, [], 0.35, 90, 5),
    ("Cozy Night In Gift Set", "Gifts", 64, [], 0.45, 25, 6),
    ("Personalized Cutting Board", "Gifts", 74, [], 0.5, 1, 3),
    ("Handmade Coaster Set", "Woodwork", 29, [], 0.3, 22, 4),
    ("Copper Wind Chime", "Gifts", 54, [], 0.5, 5, 2),
]
CATEGORY_TREE = [("Handicrafts", None), ("Woodwork", "Handicrafts"), ("Ceramics", "Handicrafts"), ("Antiques", None),
                 ("Vintage Finds", "Antiques"), ("Home Decor", None), ("Wall Art", "Home Decor"), ("Candles", "Home Decor"),
                 ("Gifts", None)]

q2 = Decimal("0.01")


def money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(q2, rounding=ROUND_HALF_UP)


def pick(rng: random.Random, weighted: list[tuple[Any, int]]) -> Any:
    total = sum(w for _, w in weighted)
    roll = rng.uniform(0, total)
    for item, weight in weighted:
        roll -= weight
        if roll <= 0:
            return item
    return weighted[-1][0]


def at(rng: random.Random, day: date, now: datetime) -> datetime:
    """A moment on `day` (US Central roughly), busier in the evening, never in the future."""
    hour = pick(rng, [(h, w) for h, w in zip(range(7, 24), [2, 3, 4, 5, 5, 6, 6, 6, 6, 7, 8, 9, 10, 9, 6, 3, 1], strict=True)])
    moment = datetime(day.year, day.month, day.day, hour, rng.randint(0, 59), rng.randint(0, 59), tzinfo=timezone.utc) + timedelta(hours=5)
    return min(moment, now - timedelta(minutes=2))


def build(now: datetime | None = None, days: int = 120, seed: int = 2) -> Rows:
    """The whole data set as {table: [row dicts]}. Deterministic for a given (now, days, seed)."""
    rng = random.Random(seed)
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    rows: Rows = {t: [] for t in (
        "categories", "products", "sales", "coupons", "cart_rules", "analytics_sessions", "orders", "order_items", "payments", "order_events",
        "coupon_redemptions", "analytics_events", "carts", "reviews", "newsletter_subscribers", "stock_alerts", "campaigns", "consent_daily",
    )}
    next_id = {t: BASE_ID for t in rows}

    def new_id(table: str) -> int:
        next_id[table] += 1
        return next_id[table]

    # ---- categories and products ---------------------------------------------------------------
    cat_ids: dict[str, int] = {}
    cat_paths: dict[str, str] = {}
    for name, parent in CATEGORY_TREE:
        cid = new_id("categories")
        cat_ids[name] = cid
        cat_paths[name] = f"{cat_paths[parent]}.{cid}" if parent else str(cid)
        rows["categories"].append({
            "id": cid, "parent_id": cat_ids.get(parent) if parent else None, "name": name, "slug": f"demo-{name.lower().replace(' ', '-')}",
            "path": cat_paths[name], "sort_order": cid - BASE_ID, "is_active": True, "created_at": now - timedelta(days=days + 30),
        })

    leaves: list[dict[str, Any]] = []  # what can be bought: a variant or a simple product
    parents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    for index, (title, category, price, variants, cost_ratio, stock, popularity) in enumerate(CATALOG, start=1):
        pid = new_id("products")
        created = now - timedelta(days=days + 20 - index * 2)
        base = {
            "category_id": cat_ids[category], "currency": "USD", "status": "published", "source": "demo", "published_at": created,
            "created_at": created, "updated_at": created, "attributes": {}, "images": [], "tags": ["handmade", category.lower()],
            "units_sold": 0, "rating_avg": Decimal("0"), "rating_count": 0, "stock_status": "in_stock",
        }
        parent = {**base, "id": pid, "parent_id": None, "sku": f"DEMO-{index:03d}", "slug": f"demo-{title.lower().replace(' ', '-')}", "title": title,
                  "description": f"{title}. A demonstration product for the sample shop history.", "base_price": money(price),
                  "compare_at_price": None, "cost_price": money(price * cost_ratio) if cost_ratio else None,
                  "stock_quantity": None if variants else stock, "popularity": popularity}
        parents.append(parent)
        if variants:
            for v, (label, vprice) in enumerate(variants, start=1):
                vid = new_id("products")
                leaf = {**base, "id": vid, "parent_id": pid, "sku": f"DEMO-{index:03d}-{v}", "slug": f"{parent['slug']}-{label.lower().replace(' ', '-')}",
                        "title": f"{title} - {label}", "description": None, "base_price": money(vprice), "compare_at_price": None,
                        "cost_price": money(vprice * cost_ratio) if cost_ratio else None, "stock_quantity": max(0, stock // len(variants) + (v == 1) * 0),
                        "attributes": {"Option": label}, "popularity": popularity, "root": parent}
                leaves.append(leaf)
                children.append(leaf)
        else:
            parent["root"] = parent
            leaves.append(parent)
    for leaf in leaves:
        if leaf["stock_quantity"] is not None and leaf["stock_quantity"] <= 0:
            leaf["stock_status"] = "out_of_stock"
    # the page needs a stock status on parents with variants too
    for parent in parents:
        kids = [lf for lf in leaves if lf["parent_id"] == parent["id"]]
        if kids and all(k["stock_status"] == "out_of_stock" for k in kids):
            parent["stock_status"] = "out_of_stock"
    leaf_weights = [(lf, lf["popularity"]) for lf in leaves if lf["stock_status"] != "out_of_stock"]

    # ---- promotions ---------------------------------------------------------------------------
    sale_id = new_id("sales")
    sale_start, sale_end = now - timedelta(days=24), now + timedelta(days=9)
    rows["sales"].append({
        "id": sale_id, "name": "Autumn makers sale", "badge": "10% off", "description": "A seasonal offer on handmade woodwork.", "kind": "percent",
        "value": Decimal("10.00"), "scope": "category", "category_ids": [cat_ids["Woodwork"]], "product_ids": [], "exclude_product_ids": [],
        "starts_at": sale_start, "ends_at": sale_end, "is_active": True, "translations": {}, "created_at": sale_start - timedelta(days=2),
    })
    old_sale = new_id("sales")
    rows["sales"].append({
        "id": old_sale, "name": "Summer clearance", "badge": "$10 off", "description": None, "kind": "fixed", "value": Decimal("10.00"), "scope": "category",
        "category_ids": [cat_ids["Gifts"]], "product_ids": [], "exclude_product_ids": [], "starts_at": now - timedelta(days=100),
        "ends_at": now - timedelta(days=70), "is_active": True, "translations": {}, "created_at": now - timedelta(days=102),
    })
    for name, rule_kind, threshold, value in (("Free shipping over $100", "free_shipping", 100, 0), ("Spend $250, save 5%", "spend_percent", 250, 5)):
        rows["cart_rules"].append({
            "id": new_id("cart_rules"), "name": name, "kind": rule_kind, "threshold_amount": money(threshold), "value": money(value), "scope": "order",
            "category_ids": [], "product_ids": [], "exclude_sale_items": False, "is_active": True, "priority": 0, "translations": {},
            "created_at": now - timedelta(days=days + 5),
        })
    coupon_defs = [("SPRING10", "percent", 10, "spring", "manual"), ("FREESHIP", "free_shipping", 0, "partners", "manual"), ("GENTLE15", "percent", 15, "winback", "manual")]
    coupons: dict[str, dict[str, Any]] = {}
    for code, kind, value, campaign, source in coupon_defs:
        c = {"id": new_id("coupons"), "code": code, "name": code.title(), "kind": kind, "value": money(value), "min_subtotal": money(0), "scope": "order",
             "category_ids": [], "product_ids": [], "exclude_sale_items": False, "first_order_only": False, "campaign": campaign, "source": source,
             "stackable": False, "is_active": True, "used_count": 0, "created_at": now - timedelta(days=days), "usage_limit": None}
        coupons[code] = c
        rows["coupons"].append(c)

    # ---- customers, orders ---------------------------------------------------------------------
    customers: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    start_day = (now - timedelta(days=days)).date()
    for offset in range(days + 1):
        day = start_day + timedelta(days=offset)
        mu = 1.0 + 0.022 * offset + (0.7 if day.weekday() in (5, 6) else 0) + (2.5 if offset in (days // 3, days - 12) else 0)
        for _ in range(max(0, round(rng.gauss(mu, 1.1)))):
            placed = at(rng, day, now)
            repeat = [c for c in customers if (placed - c["last_at"]).days > 21]
            if repeat and rng.random() < 0.2:
                customer = rng.choice(repeat)
            else:
                first, last = rng.choice(FIRST), rng.choice(LAST)
                state = pick(rng, STATES)
                customer = {"email": f"{first}.{last}{len(customers) + 1}{DEMO_EMAIL}".lower(), "name": f"{first} {last}", "state": state, "last_at": placed, "orders": 0}
                customers.append(customer)
            customer["last_at"], customer["orders"] = placed, customer["orders"] + 1
            orders.append(_order(rng, rows, new_id, leaf_weights, customer, placed, sale_id, sale_start, sale_end, cat_ids["Woodwork"], coupons))

    for order in orders:
        _finish_order(rng, rows, order, new_id, now)

    # ---- web visits ------------------------------------------------------------------------------
    root_of = {lf["id"]: lf["root"]["id"] for lf in leaves}
    _sessions(rng, rows, orders, parents, root_of, new_id, now, days)
    _carts(rng, rows, orders, new_id, now)
    _reviews(rng, rows, orders, root_of, new_id, now)
    _lists(rng, rows, customers, leaves, new_id, now, days)

    # ---- totals that the application keeps up to date ------------------------------------------
    sold: dict[int, int] = {}
    paid = {o["id"] for o in orders if o["paid_at"] is not None and o["status"] != "cancelled"}
    for item in rows["order_items"]:
        if item["order_id"] in paid:
            sold[item["product_id"]] = sold.get(item["product_id"], 0) + item["quantity"]
    for leaf in leaves:
        leaf["units_sold"] = sold.get(leaf["id"], 0)
    for parent in parents:
        if parent["id"] not in {lf["id"] for lf in leaves}:
            parent["units_sold"] = sum(sold.get(lf["id"], 0) for lf in children if lf["parent_id"] == parent["id"])
    for coupon in rows["coupons"]:
        coupon["used_count"] = sum(1 for r in rows["coupon_redemptions"] if r["coupon_id"] == coupon["id"])
    approved: dict[int, list[int]] = {}
    for r in rows["reviews"]:
        if r["status"] == "approved":
            approved.setdefault(r["product_id"], []).append(r["rating"])
    for product in parents + children:
        ratings = approved.get(product["id"], [])
        product["rating_count"] = len(ratings)
        product["rating_avg"] = money(sum(ratings) / len(ratings)) if ratings else Decimal("0.00")
    rows["products"] = [{k: v for k, v in p.items() if k not in ("popularity", "root")} for p in parents + children]
    rows["consent_daily"] = [
        {"day": (now - timedelta(days=i)).date(), "accepted": rng.randint(18, 50), "declined": rng.randint(8, 30)} for i in range(min(days, 90))
    ]
    return rows


# ---------------------------------------------------------------------------------------------------
def _order(rng, rows, new_id, leaf_weights, customer, placed, sale_id, sale_start, sale_end, adult_cat, coupons):
    oid = new_id("orders")
    wanted = 1 + (rng.random() < 0.28) + (rng.random() < 0.08)
    chosen: list[dict[str, Any]] = []
    for _ in range(wanted):
        leaf = pick(rng, leaf_weights)
        if leaf not in chosen:
            chosen.append(leaf)
    on_sale = sale_start <= placed < sale_end
    lines = []
    for leaf in chosen:
        qty = 2 if rng.random() < 0.1 else 1
        list_price = leaf["base_price"]
        unit = list_price
        used_sale = None
        if on_sale and leaf["category_id"] == adult_cat:
            unit, used_sale = money(list_price * Decimal("0.9")), sale_id
        lines.append({"leaf": leaf, "qty": qty, "unit": unit, "list": list_price, "sale": used_sale})
    subtotal = sum((ln["unit"] * ln["qty"] for ln in lines), Decimal(0))
    discounts: list[dict[str, Any]] = []
    discount = Decimal(0)
    coupon_code = None
    roll = rng.random()
    if roll < 0.11:
        coupon_code = "SPRING10"
    elif roll < 0.15:
        coupon_code = "FREESHIP"
    elif roll < 0.18:
        coupon_code = "GENTLE15"
    elif roll < 0.22:
        coupon_code = "WELCOME"
    free_ship = False
    if coupon_code == "WELCOME":
        code_id = new_id("coupons")
        code = f"WELCOME-{secrets.token_hex(3).upper()}"
        coupon = {"id": code_id, "code": code, "name": "Welcome offer", "kind": "percent", "value": money(10), "min_subtotal": money(0), "scope": "order",
                  "category_ids": [], "product_ids": [], "exclude_sale_items": False, "first_order_only": True, "campaign": "welcome", "source": "welcome",
                  "stackable": False, "is_active": True, "used_count": 0, "usage_limit": 1, "assigned_email": customer["email"],
                  "created_at": placed - timedelta(days=rng.randint(1, 9))}
        rows["coupons"].append(coupon)
        coupons[code] = coupon
        coupon_code = code
        discount = money(subtotal * Decimal("0.10"))
        discounts.append({"type": "coupon", "label": code, "code": code, "amount": float(discount)})
    elif coupon_code == "SPRING10":
        discount = money(subtotal * Decimal("0.10"))
        discounts.append({"type": "coupon", "label": "SPRING10", "code": "SPRING10", "amount": float(discount)})
    elif coupon_code == "GENTLE15":
        discount = money(subtotal * Decimal("0.15"))
        discounts.append({"type": "coupon", "label": "GENTLE15", "code": "GENTLE15", "amount": float(discount)})
    elif coupon_code == "FREESHIP":
        free_ship = True
        discounts.append({"type": "free_shipping", "label": "FREESHIP", "code": "FREESHIP", "amount": 0.0})
    if not coupon_code and subtotal >= 250 and rng.random() < 0.9:
        discount = money(subtotal * Decimal("0.05"))
        discounts.append({"type": "rule", "label": "Spend $250, save 5%", "code": None, "amount": float(discount)})
    goods = subtotal - discount
    if goods >= 100 and not free_ship:
        free_ship = True
        discounts.append({"type": "free_shipping", "label": "Free shipping over $100", "code": None, "amount": 0.0})
    shipping = Decimal(0) if free_ship else money("8.95")
    state = customer["state"]
    tax = money(goods * Decimal("0.0625")) if state == "IL" else Decimal(0)
    grand = goods + shipping + tax
    channel = pick(rng, CHANNELS)
    device = pick(rng, DEVICES)
    # spread the order-level discount over the items, like the real checkout does
    remaining = discount
    for i, ln in enumerate(lines):
        if i == len(lines) - 1:
            share = remaining
        else:
            share = money(discount * (ln["unit"] * ln["qty"]) / subtotal) if subtotal else Decimal(0)
        remaining -= share
        ln["share"] = share
    order = {
        "id": oid, "number": f"DEMO-{1000 + oid - BASE_ID}", "user_id": None, "email": customer["email"], "customer_name": customer["name"],
        "currency": "USD", "subtotal": subtotal, "tax_total": tax, "shipping_total": shipping, "discount_total": discount, "grand_total": grand,
        "shipping_address": {"full_name": customer["name"], "line1": f"{rng.randint(10, 999)} Main St", "city": CITIES.get(state, "Springfield"),
                             "region": state, "postal_code": f"{rng.randint(10000, 99999)}", "country": "US"},
        "shipping_method": "standard", "payment_provider": "stripe" if rng.random() < 0.85 else "manual", "placed_at": placed, "created_at": placed,
        "updated_at": placed, "access_token": secrets.token_urlsafe(32), "locale": pick(rng, [("en", 88), ("es", 8), ("nl", 4)]), "payment_status": "unpaid",
        "refunded_total": Decimal(0), "coupon_code": coupon_code, "discounts": discounts, "tax_rate": Decimal("6.25") if state == "IL" else Decimal(0),
        "channel": channel, "device": device, "marketing_opt_in": rng.random() < 0.35, "status": "pending", "fulfillment_status": "unfulfilled",
        "paid_at": None, "shipped_at": None, "delivered_at": None, "cancelled_at": None, "session_id": None, "_lines": lines, "_customer": customer,
    }
    return order


def _finish_order(rng, rows, order, new_id, now):
    """Give the order its payment, shipping and refund history, and write its rows."""
    placed = order["placed_at"]
    age = (now - placed).total_seconds() / 86400
    lines = order.pop("_lines")
    order.pop("_customer")
    state = "paid"
    roll = rng.random()
    if age < 1.5 and order["payment_provider"] == "manual":
        state = "unpaid"
    elif order["payment_provider"] == "manual" and roll < 0.25 and age < 6:
        state = "unpaid"
    elif roll < 0.035:
        state = "cancelled_unpaid"
    elif roll < 0.05:
        state = "cancelled_paid"
    elif roll < 0.075 and age > 12:
        state = "refunded"
    elif roll < 0.11 and age > 12:
        state = "partial_refund"
    paid_at = None if state in ("unpaid", "cancelled_unpaid") else placed + timedelta(minutes=rng.randint(1, 12))
    order["paid_at"] = paid_at
    order["payment_status"] = "unpaid" if paid_at is None else "paid"
    status = "pending" if paid_at is None else "paid"
    if paid_at and age > 1:
        shipped = paid_at + timedelta(hours=rng.randint(6, 70))
        if shipped < now and state not in ("cancelled_paid",):
            order.update(shipped_at=shipped, fulfillment_status="fulfilled", status="shipped", carrier="USPS", tracking_number=f"9400{rng.randint(10**15, 10**16 - 1)}")
            status = "shipped"
            delivered = shipped + timedelta(days=rng.randint(2, 7))
            if delivered < now:
                order.update(delivered_at=delivered)
                status = "delivered"
        elif age > 3 and state not in ("cancelled_paid",):
            status = "processing"
    elif paid_at and age > 0.3:
        status = "processing" if rng.random() < 0.4 else "paid"
    order["status"] = status
    if state == "cancelled_unpaid":
        order.update(status="cancelled", cancelled_at=placed + timedelta(minutes=95), payment_status="unpaid")
    refund_payments: list[dict[str, Any]] = []
    if state == "cancelled_paid":
        order.update(status="cancelled", cancelled_at=paid_at + timedelta(hours=rng.randint(1, 20)), shipped_at=None, delivered_at=None,
                     fulfillment_status="unfulfilled", refunded_total=order["grand_total"], payment_status="refunded")
        refund_payments.append({"amount": order["grand_total"], "at": order["cancelled_at"]})
    elif state == "refunded":
        order.update(status="refunded", refunded_total=order["grand_total"], payment_status="refunded")
        refund_payments.append({"amount": order["grand_total"], "at": paid_at + timedelta(days=rng.randint(3, 10))})
        for ln in lines:
            ln["refunded"] = ln["qty"]
    elif state == "partial_refund":
        ln = lines[0]
        amount = min(order["grand_total"], money(ln["unit"] * 1))
        order.update(refunded_total=amount, payment_status="partially_refunded")
        refund_payments.append({"amount": amount, "at": paid_at + timedelta(days=rng.randint(3, 10))})
        ln["refunded"] = 1
    rows["orders"].append(order)
    for ln in lines:
        leaf = ln["leaf"]
        rows["order_items"].append({
            "id": new_id("order_items"), "order_id": order["id"], "product_id": leaf["id"], "sku": leaf["sku"], "title": leaf["title"], "unit_price": ln["unit"],
            "quantity": ln["qty"], "line_total": ln["unit"] * ln["qty"], "attributes": leaf["attributes"], "slug": leaf["root"]["slug"], "list_price": ln["list"],
            "unit_cost": leaf["cost_price"], "sale_id": ln["sale"], "discount_total": ln["share"], "refunded_quantity": ln.get("refunded", 0),
        })
    rows["payments"].append({
        "id": new_id("payments"), "order_id": order["id"], "provider": order["payment_provider"], "kind": "charge",
        "status": "succeeded" if paid_at else ("cancelled" if order["status"] == "cancelled" else "pending"), "amount": order["grand_total"],
        "currency": "USD", "created_at": placed, "updated_at": placed, "raw": {},
    })
    for refund in refund_payments:
        rows["payments"].append({
            "id": new_id("payments"), "order_id": order["id"], "provider": order["payment_provider"], "kind": "refund", "status": "succeeded",
            "amount": refund["amount"], "currency": "USD", "created_at": refund["at"], "updated_at": refund["at"], "raw": {},
        })
    def event(kind: str, message: str, when: datetime, actor: str = "system") -> None:
        rows["order_events"].append({"id": new_id("order_events"), "order_id": order["id"], "type": kind, "message": message, "data": {},
                                     "actor": actor, "created_at": when})

    event("placed", f"Order placed ({order['payment_provider']})", placed, "customer")
    if paid_at:
        event("paid", f"Payment received via {order['payment_provider']}", paid_at)
    if order.get("shipped_at"):
        event("shipped", f"Shipped: USPS {order.get('tracking_number')}", order["shipped_at"], "Demo admin")
    if order.get("delivered_at"):
        event("delivered", "Delivered", order["delivered_at"], "Demo admin")
    for refund in refund_payments:
        event("refund", f"Refunded {refund['amount']}", refund["at"], "Demo admin")
    if order.get("cancelled_at"):
        event("cancelled", "Cancelled", order["cancelled_at"], "Demo admin")
    if order["coupon_code"] and order["coupon_code"] in {c["code"] for c in rows["coupons"]} and order["status"] != "cancelled":
        coupon = next(c for c in rows["coupons"] if c["code"] == order["coupon_code"])
        amount = next((Decimal(str(d["amount"])) for d in order["discounts"] if d.get("code") == order["coupon_code"]), Decimal(0))
        rows["coupon_redemptions"].append({"id": new_id("coupon_redemptions"), "coupon_id": coupon["id"], "order_id": order["id"], "email": order["email"],
                                           "amount": amount, "created_at": placed})


def _vitals(rng, device):
    slow = 1.35 if device == "mobile" else 1.0
    return [("LCP", round(rng.lognormvariate(math.log(2100 * slow), 0.35))), ("FCP", round(rng.lognormvariate(math.log(1200 * slow), 0.3))),
            ("TTFB", round(rng.lognormvariate(math.log(380), 0.4))), ("CLS", round(abs(rng.gauss(0.045, 0.04)), 3)),
            ("INP", round(rng.lognormvariate(math.log(140 * slow), 0.4)))]


def _session(rng, rows, new_id, visitors, when, channel=None, device=None, converted=False):
    sid = f"demo_{secrets.token_hex(10)}"
    channel = channel or pick(rng, CHANNELS)
    device = device or pick(rng, DEVICES)
    returning = visitors and rng.random() < 0.28
    visitor = rng.choice(visitors) if returning else f"demo_v{secrets.token_hex(8)}"
    if not returning:
        visitors.append(visitor)
    pv = 1 if (not converted and rng.random() < 0.38) else rng.randint(2, 9)
    host = rng.choice(REFERRERS.get(channel, [None]))
    utm = (("newsletter", "email", "fall-thank-you") if channel == "email" else ("google", "cpc", "shop-brand") if channel == "paid_search" else (None, None, None))
    duration = 0 if pv == 1 else rng.randint(40, 900)
    rows["analytics_sessions"].append({
        "id": sid, "visitor_id": visitor, "started_at": when, "last_seen_at": when + timedelta(seconds=duration),
        "landing_path": rng.choice(["/", "/", "/shop", "/category/woodwork", "/product/hand-turned-walnut-bowl", "/product/soy-candle-trio"]),
        "referrer_host": host, "channel": channel, "utm_source": utm[0], "utm_medium": utm[1], "utm_campaign": utm[2], "device": device,
        "browser": pick(rng, BROWSERS), "os": pick(rng, OSES[device]), "locale": pick(rng, [("en", 90), ("es", 7), ("nl", 3)]),
        "is_new_visitor": not returning, "page_views": pv, "event_count": 0,
    })
    return rows["analytics_sessions"][-1], pv


def _event(rows, new_id, session, kind, when, path=None, product=None, value=None, data=None):
    rows["analytics_events"].append({
        "id": new_id("analytics_events"), "session_id": session["id"], "type": kind, "path": path, "product_id": product, "value": value, "data": data or {},
        "created_at": when,
    })
    session["event_count"] += 1


def _sessions(rng, rows, orders, parents, root_of, new_id, now, days):
    visitors: list[str] = []
    popular = [(p["id"], p["popularity"]) for p in parents]
    for order in orders:
        if rng.random() > 0.55:  # the others declined analytics
            continue
        when = order["placed_at"] - timedelta(minutes=rng.randint(6, 45))
        session, pv = _session(rng, rows, new_id, visitors, when, order["channel"], order["device"], converted=True)
        order["session_id"] = session["id"]
        items = [i for i in rows["order_items"] if i["order_id"] == order["id"]]
        for _ in range(pv):
            _event(rows, new_id, session, "page_view", when, "/shop")
        for item in items:
            root = root_of[item["product_id"]]
            _event(rows, new_id, session, "product_view", when + timedelta(minutes=1), f"/product/{item['slug']}", root)
            _event(rows, new_id, session, "add_to_cart", when + timedelta(minutes=3), f"/product/{item['slug']}", root, item["unit_price"], {"qty": item["quantity"]})
        _event(rows, new_id, session, "begin_checkout", when + timedelta(minutes=5), "/checkout", None, order["subtotal"])
        session["last_seen_at"] = order["placed_at"]
    for offset in range(days + 1):
        day = (now - timedelta(days=days)).date() + timedelta(days=offset)
        for _ in range(max(6, round(rng.gauss(14 + 0.28 * offset, 4)))):
            when = at(rng, day, now)
            session, pv = _session(rng, rows, new_id, visitors, when)
            for _ in range(pv):
                _event(rows, new_id, session, "page_view", when, rng.choice(["/", "/shop", "/category/woodwork", "/category/home-decor", "/about", "/contact"]))
            if rng.random() < 0.55:
                for _ in range(rng.randint(1, 3)):
                    pid = pick(rng, popular)
                    slug = next(p["slug"] for p in parents if p["id"] == pid)
                    _event(rows, new_id, session, "product_view", when, f"/product/{slug}", pid)
                    if rng.random() < 0.2:
                        _event(rows, new_id, session, "add_to_cart", when, f"/product/{slug}", pid, money(50), {"qty": 1})
                        if rng.random() < 0.35:
                            _event(rows, new_id, session, "begin_checkout", when, "/checkout", None, money(80))
                    if rng.random() < 0.04:
                        _event(rows, new_id, session, "wishlist_add", when, f"/product/{slug}", pid)
            if rng.random() < 0.09:
                term = pick(rng, SEARCHES)
                _event(rows, new_id, session, "search", when, "/search", None, None, {"q": term, "results": 0 if term in ZERO_RESULT_TERMS else rng.randint(1, 9)})
            if rng.random() < 0.02:
                _event(rows, new_id, session, "newsletter_signup", when, "/")
            if rng.random() < 0.35:
                for name, value in _vitals(rng, session["device"]):
                    _event(rows, new_id, session, "web_vital", when, "/shop", None, Decimal(str(value)), {"name": name})


def _carts(rng, rows, orders, new_id, now):
    for order in orders:
        items = [i for i in rows["order_items"] if i["order_id"] == order["id"]]
        recovered = order["paid_at"] is not None and rng.random() < 0.06
        started = order["placed_at"] - timedelta(minutes=rng.randint(5, 40 if not recovered else 2000))
        cart = {
            "id": new_id("carts"), "token": f"demo-{secrets.token_urlsafe(18)}", "email": order["email"] if recovered else None, "locale": order["locale"],
            "items": [{"product_id": i["product_id"], "quantity": i["quantity"], "options": {}} for i in items],
            "item_count": sum(i["quantity"] for i in items), "subtotal": order["subtotal"], "coupon_code": None, "session_id": order["session_id"],
            "reminders_ok": recovered, "last_activity_at": order["placed_at"], "checkout_started_at": order["placed_at"] - timedelta(minutes=2),
            "converted_order_id": order["id"], "converted_at": order["placed_at"], "reminder_count": 1 if recovered else 0,
            "last_reminder_at": order["placed_at"] - timedelta(hours=3) if recovered else None, "created_at": started, "updated_at": order["placed_at"],
        }
        rows["carts"].append(cart)
    prices = [(i["product_id"], i["unit_price"]) for i in rows["order_items"]]
    for _ in range(round(len(orders) * 3.1)):
        when = now - timedelta(minutes=rng.randint(30, 60 * 24 * 118))
        picks = [rng.choice(prices) for _ in range(rng.choice([1, 1, 1, 2, 3]))]
        age_h = (now - when).total_seconds() / 3600
        consent = rng.random() < 0.35
        reminders = 0
        if consent and age_h > 24:
            reminders = 2 if age_h > 96 and rng.random() < 0.7 else 1
        rows["carts"].append({
            "id": new_id("carts"), "token": f"demo-{secrets.token_urlsafe(18)}", "email": f"{secrets.token_hex(3)}{DEMO_EMAIL}" if consent else None,
            "locale": "en", "items": [{"product_id": pid, "quantity": 1, "options": {}} for pid, _ in picks], "item_count": len(picks),
            "subtotal": sum((p for _, p in picks), Decimal(0)), "coupon_code": None, "session_id": None, "reminders_ok": consent, "last_activity_at": when,
            "checkout_started_at": when - timedelta(minutes=2) if rng.random() < 0.22 else None, "converted_order_id": None, "converted_at": None,
            "reminder_count": reminders, "last_reminder_at": when + timedelta(hours=24 * reminders) if reminders else None, "created_at": when - timedelta(minutes=10),
            "updated_at": when,
        })


def _reviews(rng, rows, orders, root_of, new_id, now):
    by_order: dict[int, list[dict[str, Any]]] = {}
    for item in rows["order_items"]:
        by_order.setdefault(item["order_id"], []).append(item)
    for order in orders:
        if order["delivered_at"] is None or order["status"] != "delivered" or rng.random() > 0.38:
            continue
        item = rng.choice(by_order[order["id"]])
        when = order["delivered_at"] + timedelta(days=rng.randint(3, 14))
        if when > now:
            continue
        rating = pick(rng, [(1, 3), (2, 4), (3, 8), (4, 25), (5, 60)])
        status = pick(rng, [("approved", 80), ("pending", 15), ("rejected", 5)])
        text = {5: "Beautiful craftsmanship and it arrived quickly. Exactly what we hoped for.", 4: "Lovely piece, packaging was careful. Slightly smaller than I pictured.",
                3: "It is fine. Shipping took longer than expected.", 2: "The finish had a scratch and the lid fit loosely.", 1: "Not what the photos showed. Disappointed."}[rating]
        first, last = order["customer_name"].split(" ", 1)
        answered = rating <= 2 and status == "approved"
        rows["reviews"].append({
            "id": new_id("reviews"), "product_id": root_of[item["product_id"]], "order_id": order["id"], "author_name": f"{first} {last[0]}.",
            "rating": rating, "title": {5: "Perfect", 4: "Very nice", 3: "Okay", 2: "Disappointing", 1: "Poor"}[rating], "body": text, "locale": "en", "status": status,
            "verified": True, "helpful_count": rng.randint(0, 6), "reply": "Thank you for telling us. We are sorry to hear that and have written to you." if answered else None,
            "replied_at": when + timedelta(days=1) if answered else None, "created_at": when, "updated_at": when,
        })


def _lists(rng, rows, customers, leaves, new_id, now, days):
    for i, customer in enumerate(customers[: round(len(customers) * 0.5)]):
        rows["newsletter_subscribers"].append({
            "id": new_id("newsletter_subscribers"), "email": customer["email"], "locale": "en", "source": "checkout" if i % 2 else "site",
            "unsubscribe_token": secrets.token_urlsafe(24), "unsubscribed_at": now - timedelta(days=rng.randint(1, 30)) if rng.random() < 0.07 else None,
            "created_at": customer["last_at"] - timedelta(days=rng.randint(0, 40)), "updated_at": now,
        })
    for i in range(70):
        rows["newsletter_subscribers"].append({
            "id": new_id("newsletter_subscribers"), "email": f"visitor{i}{DEMO_EMAIL}", "locale": pick(rng, [("en", 85), ("es", 10), ("nl", 5)]),
            "source": pick(rng, [("site", 70), ("cart_reminder", 20), ("order", 10)]), "unsubscribe_token": secrets.token_urlsafe(24),
            "unsubscribed_at": now - timedelta(days=rng.randint(1, 20)) if rng.random() < 0.06 else None,
            "created_at": now - timedelta(days=rng.randint(0, days)), "updated_at": now,
        })
    out_of_stock = [lf for lf in leaves if lf["stock_status"] == "out_of_stock"]
    for lf in out_of_stock:
        for j in range(rng.randint(2, 5)):
            rows["stock_alerts"].append({"id": new_id("stock_alerts"), "product_id": lf["id"], "email": f"waiting{j}{lf['id']}{DEMO_EMAIL}", "locale": "en",
                                         "created_at": now - timedelta(days=rng.randint(1, 25))})
    sent = now - timedelta(days=18)
    rows["campaigns"].append({
        "id": new_id("campaigns"), "name": "Autumn thank-you", "subject": "A small thank-you from WindyCityWares", "body": "Thank you for trusting us with something so personal.",
        "translations": {}, "segment": "customers", "coupon_kind": "percent", "coupon_value": money(10), "coupon_expires_days": 14, "coupon_min_subtotal": money(0),
        "status": "sent", "recipients": 64, "sent_at": sent, "created_at": sent - timedelta(days=2), "updated_at": sent,
    })


# ---------------------------------------------------------------------------------------------------
INSERT_ORDER = [
    "categories", "products", "sales", "coupons", "cart_rules", "analytics_sessions", "orders", "order_items", "payments", "order_events",
    "coupon_redemptions", "analytics_events", "carts", "reviews", "newsletter_subscribers", "stock_alerts", "campaigns", "consent_daily",
]


async def remove() -> None:
    from sqlalchemy import text

    from app.core.database import SessionFactory

    async with SessionFactory() as session:
        for sql in (
            "DELETE FROM carts WHERE token LIKE 'demo-%'",
            "DELETE FROM analytics_sessions WHERE id LIKE 'demo_%'",
            "DELETE FROM orders WHERE number LIKE 'DEMO-%'",
            "DELETE FROM coupons WHERE id > :base",
            "DELETE FROM campaigns WHERE id > :base",
            "DELETE FROM newsletter_subscribers WHERE email LIKE '%@demo.example'",
            "DELETE FROM stock_alerts WHERE email LIKE '%@demo.example'",
            "DELETE FROM sales WHERE id > :base",
            "DELETE FROM cart_rules WHERE id > :base",
            "DELETE FROM reviews WHERE id > :base",
            "DELETE FROM products WHERE sku LIKE 'DEMO-%' AND parent_id IS NOT NULL",
            "DELETE FROM products WHERE sku LIKE 'DEMO-%'",
            "DELETE FROM categories WHERE slug LIKE 'demo-%' AND parent_id IS NOT NULL",
            "DELETE FROM categories WHERE slug LIKE 'demo-%'",
        ):
            await session.execute(text(sql), {"base": BASE_ID} if ":base" in sql else {})
        await session.commit()


async def load(rows: Rows) -> None:
    from sqlalchemy import insert

    from app.core.database import SessionFactory
    from app.models.base import Base

    # Registering every model makes Base.metadata know all tables.
    import app.models  # noqa: F401

    await remove()
    async with SessionFactory() as session:
        for name in INSERT_ORDER:
            data = rows[name]
            if not data:
                continue
            table = Base.metadata.tables[name]
            columns = {c.name for c in table.columns}
            clean = [{k: v for k, v in row.items() if k in columns} for row in data]
            # every row of one insert must carry the same keys
            keys = sorted({k for row in clean for k in row})
            clean = [{k: row.get(k) for k in keys} for row in clean]
            for start in range(0, len(clean), 400):
                await session.execute(insert(table), clean[start : start + 400])
        await session.commit()


async def main(argv: list[str] | None = None) -> None:
    from app.core.config import get_settings

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--remove", action="store_true", help="delete the demo data instead of adding it")
    parser.add_argument("--days", type=int, default=120)
    args = parser.parse_args(argv)
    if get_settings().is_production:
        raise SystemExit("Refusing to run: demo data must never be added to the live shop.")
    if args.remove:
        await remove()
        print("Demo data removed.")
        return
    rows = build(days=args.days)
    await load(rows)
    print({k: len(v) for k, v in rows.items()})


if __name__ == "__main__":
    asyncio.run(main())
