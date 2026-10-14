"""Pricing for the shop: sales, coupons, shipping and tax.

Pure Python (no database, no web framework), so every rule can be tested on its own. The services
load rules from the database, turn them into the small dataclasses below, and call `price_cart`.

How a price is built, in order:

1. Sale: each line takes the best live sale that applies to it (sales never stack).
2. Coupon: one code per order, applied to the lines it covers; the discount is shared across those
   lines in whole cents, so the lines always add up to the order total.
3. Shipping: the chosen method's price, free when the order is over the method's free-shipping
   amount or the coupon gives free shipping.
4. Tax: every matching tax rate, on the goods after discounts (and on shipping when the rate says so).

All amounts are `Decimal` with two places, rounded half-up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
HUNDRED = Decimal(100)

PERCENT = "percent"
FIXED = "fixed"
FREE_SHIPPING = "free_shipping"


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value) if isinstance(value, float) else value).quantize(CENT, rounding=ROUND_HALF_UP)


def percent_of(amount: Decimal, percent: Decimal) -> Decimal:
    return money(amount * percent / HUNDRED)


def allocate(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split `total` across `weights` in whole cents (largest remainder), so the parts add up exactly."""
    cents = int((total * 100).to_integral_value(rounding=ROUND_HALF_UP))
    w = [int((x * 100).to_integral_value(rounding=ROUND_HALF_UP)) for x in weights]
    weight_sum = sum(w)
    if cents <= 0 or weight_sum <= 0:
        return [ZERO for _ in weights]
    shares = [cents * x // weight_sum for x in w]
    leftover = cents - sum(shares)
    by_remainder = sorted(range(len(w)), key=lambda i: (-(cents * w[i] % weight_sum), i))
    for i in by_remainder[:leftover]:
        shares[i] += 1
    return [Decimal(s) / 100 for s in shares]


def path_within(path: str | None, root: str | None) -> bool:
    """True when category `path` ("1.4.9") is `root` ("1.4") or lies beneath it."""
    if not path or not root:
        return False
    return path == root or path.startswith(f"{root}.")


def _aware(moment: datetime | None) -> datetime | None:
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment


# --- what can be bought ------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    key: str
    product_id: int
    unit_price: Decimal  # list price
    quantity: int
    parent_id: int | None = None  # set for variants: a sale on the parent covers them too
    category_path: str | None = None


@dataclass(frozen=True)
class Scope:
    """Which products a sale or coupon covers."""

    kind: str = "all"  # all | category | products
    category_path: str | None = None
    product_ids: frozenset[int] = frozenset()

    def covers(self, line: Line) -> bool:
        if self.kind == "all":
            return True
        if self.kind == "products":
            return line.product_id in self.product_ids or (line.parent_id is not None and line.parent_id in self.product_ids)
        if self.kind == "category":
            return path_within(line.category_path, self.category_path)
        return False


# --- sales -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Sale:
    id: int
    name: str
    kind: str  # percent | fixed
    value: Decimal
    scope: Scope = Scope()
    label: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    active: bool = True

    def is_live(self, now: datetime) -> bool:
        start, end = _aware(self.starts_at), _aware(self.ends_at)
        return self.active and (start is None or start <= now) and (end is None or now < end)

    def price_for(self, list_price: Decimal) -> Decimal:
        if self.kind == PERCENT:
            off = percent_of(list_price, min(self.value, HUNDRED))
        else:
            off = min(money(self.value), list_price)
        return max(ZERO, list_price - off)


def best_sale(line: Line, sales: list[Sale] | tuple[Sale, ...], now: datetime) -> tuple[Sale | None, Decimal]:
    """The live sale giving the customer the lowest price (ties go to the oldest sale), or (None, list price)."""
    best: Sale | None = None
    best_price = line.unit_price
    for sale in sorted(sales, key=lambda s: s.id):
        if not sale.is_live(now) or not sale.scope.covers(line):
            continue
        price = sale.price_for(line.unit_price)
        if price < best_price:
            best, best_price = sale, price
    return best, best_price


# --- coupons -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Coupon:
    id: int
    code: str
    kind: str  # percent | fixed | free_shipping
    value: Decimal = ZERO
    min_subtotal: Decimal | None = None
    max_discount: Decimal | None = None
    scope: Scope = Scope()
    exclude_sale_items: bool = False
    first_order_only: bool = False
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    active: bool = True
    usage_limit: int | None = None
    used_count: int = 0
    per_customer_limit: int | None = None
    # Personal coupons only work for this account or email address.
    user_id: int | None = None
    email: str | None = None


@dataclass(frozen=True)
class Shopper:
    user_id: int | None = None
    email: str | None = None
    prior_orders: int = 0  # paid or open orders already placed by this person
    coupon_uses: int = 0  # times this person has already used the coupon being checked


@dataclass(frozen=True)
class Problem:
    """Why a coupon was not applied. `code` is stable (the storefront translates it); `message` is English."""

    code: str
    message: str
    data: dict[str, str] = field(default_factory=dict)


def _symbol(currency: str) -> str:
    return {"USD": "$", "CAD": "CA$", "EUR": "€", "GBP": "£"}.get(currency, f"{currency} ")


def check_coupon(coupon: Coupon, shopper: Shopper, now: datetime) -> Problem | None:
    """Everything about a coupon that doesn't depend on the cart's contents."""
    invalid = Problem("invalid", "That code isn't valid.")
    if not coupon.active:
        return invalid
    start, end = _aware(coupon.starts_at), _aware(coupon.expires_at)
    if start is not None and now < start:
        return Problem("not_started", "This code isn't active yet.")
    if end is not None and now >= end:
        return Problem("expired", "This code has expired.")
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        return Problem("used_up", "This code has already been used up.")
    if coupon.user_id is not None or coupon.email:
        by_user = coupon.user_id is not None and shopper.user_id == coupon.user_id
        by_email = bool(coupon.email) and bool(shopper.email) and shopper.email.strip().lower() == coupon.email.strip().lower()
        if not (by_user or by_email):
            if shopper.user_id is None and not shopper.email and coupon.email:
                return Problem("needs_email", "This code belongs to an email address. It will apply at checkout once you enter that email.")
            return invalid  # same answer as an unknown code, so codes can't be probed
    if coupon.first_order_only and shopper.prior_orders > 0:
        return Problem("first_order_only", "This code is for a first order only.")
    if coupon.per_customer_limit is not None and shopper.coupon_uses >= coupon.per_customer_limit:
        return Problem("already_used", "You've already used this code.")
    return None


# --- shipping and tax --------------------------------------------------------------------------


@dataclass(frozen=True)
class ShippingOption:
    code: str
    name: str
    price: Decimal
    free_over: Decimal | None = None
    min_days: int | None = None
    max_days: int | None = None
    countries: frozenset[str] = frozenset()  # empty = everywhere

    def serves(self, country: str | None) -> bool:
        return not self.countries or (country or "").upper() in self.countries


@dataclass(frozen=True)
class Destination:
    country: str | None = None
    region: str | None = None
    postal_code: str | None = None


@dataclass(frozen=True)
class TaxRate:
    id: int
    name: str
    country: str
    rate: Decimal  # percent, e.g. 6.25
    region: str | None = None  # None = the whole country
    applies_to_shipping: bool = False

    def matches(self, dest: Destination) -> bool:
        if not dest.country or self.country.upper() != dest.country.upper():
            return False
        if self.region is None:
            return True
        return bool(dest.region) and self.region.strip().casefold() == dest.region.strip().casefold()


# --- the result --------------------------------------------------------------------------------


@dataclass
class PricedLine:
    key: str
    product_id: int
    quantity: int
    list_price: Decimal
    unit_price: Decimal  # after any sale
    sale_id: int | None = None
    sale_label: str | None = None
    coupon_discount: Decimal = ZERO

    @property
    def list_total(self) -> Decimal:
        return money(self.list_price * self.quantity)

    @property
    def line_total(self) -> Decimal:
        return money(self.unit_price * self.quantity)

    @property
    def net_total(self) -> Decimal:
        """What the customer pays for the line before shipping and tax."""
        return self.line_total - self.coupon_discount


@dataclass
class ShippingQuote:
    code: str
    name: str
    base_price: Decimal
    price: Decimal  # what it costs this order (0 when free)
    free: bool
    min_days: int | None = None
    max_days: int | None = None


@dataclass
class TaxLine:
    name: str
    rate: Decimal
    amount: Decimal


@dataclass
class Quote:
    currency: str
    lines: list[PricedLine]
    list_subtotal: Decimal
    subtotal: Decimal  # after sales
    sale_savings: Decimal
    coupon_code: str | None
    coupon_discount: Decimal
    coupon_free_shipping: bool
    coupon_problem: Problem | None
    shipping_options: list[ShippingQuote]
    shipping_method: str | None
    shipping_total: Decimal
    shipping_discount: Decimal  # what free shipping saved the customer
    tax_lines: list[TaxLine]
    tax_total: Decimal
    total: Decimal
    free_shipping_threshold: Decimal | None
    free_shipping_remaining: Decimal | None

    @property
    def discount_total(self) -> Decimal:
        """Everything taken off: sale savings, coupon and free shipping."""
        return self.sale_savings + self.coupon_discount + self.shipping_discount

    @property
    def goods_after_discounts(self) -> Decimal:
        return self.subtotal - self.coupon_discount


# --- the calculation ---------------------------------------------------------------------------


def price_cart(
    lines: list[Line],
    *,
    sales: list[Sale] | tuple[Sale, ...] = (),
    coupon: Coupon | None = None,
    shopper: Shopper = Shopper(),
    shipping: list[ShippingOption] | tuple[ShippingOption, ...] = (),
    shipping_code: str | None = None,
    destination: Destination = Destination(),
    tax_rates: list[TaxRate] | tuple[TaxRate, ...] = (),
    now: datetime | None = None,
    currency: str = "USD",
) -> Quote:
    now = now or datetime.now(timezone.utc)
    for line in lines:
        if line.quantity < 1:
            raise ValueError("quantity must be at least 1")
        if line.unit_price < 0:
            raise ValueError("price can't be negative")

    # 1. Sales
    priced: list[PricedLine] = []
    for line in lines:
        sale, unit = best_sale(line, sales, now)
        priced.append(PricedLine(
            key=line.key, product_id=line.product_id, quantity=line.quantity, list_price=money(line.unit_price),
            unit_price=unit, sale_id=sale.id if sale else None, sale_label=(sale.label or sale.name) if sale else None,
        ))
    list_subtotal = sum((p.list_total for p in priced), ZERO)
    subtotal = sum((p.line_total for p in priced), ZERO)

    # 2. Coupon
    coupon_discount = ZERO
    free_shipping_coupon = False
    problem: Problem | None = None
    applied_code: str | None = None
    if coupon is not None:
        problem = check_coupon(coupon, shopper, now)
        if problem is None:
            eligible = [(i, p) for i, p in enumerate(priced)
                        if coupon.scope.covers(lines[i]) and not (coupon.exclude_sale_items and p.sale_id is not None)]
            eligible_total = sum((p.line_total for _, p in eligible), ZERO)
            if eligible_total <= 0:
                problem = Problem("no_eligible_items", "This code doesn't apply to the items in your cart.")
            elif coupon.min_subtotal is not None and eligible_total < coupon.min_subtotal:
                need = f"{_symbol(currency)}{money(coupon.min_subtotal)}"
                problem = Problem("min_subtotal", f"Spend {need} or more on eligible items to use this code.",
                                  {"min": str(money(coupon.min_subtotal))})
            elif coupon.kind == FREE_SHIPPING:
                free_shipping_coupon = True
                applied_code = coupon.code
            else:
                if coupon.kind == PERCENT:
                    raw = percent_of(eligible_total, min(coupon.value, HUNDRED))
                else:
                    raw = money(coupon.value)
                if coupon.max_discount is not None:
                    raw = min(raw, money(coupon.max_discount))
                coupon_discount = min(raw, eligible_total)
                shares = allocate(coupon_discount, [p.line_total for _, p in eligible])
                for (_, p), share in zip(eligible, shares):
                    p.coupon_discount = share
                applied_code = coupon.code

    goods = subtotal - coupon_discount

    # 3. Shipping
    available = [o for o in shipping if o.serves(destination.country)]
    options: list[ShippingQuote] = []
    for o in available:
        free = free_shipping_coupon or (o.free_over is not None and goods >= o.free_over)
        options.append(ShippingQuote(
            code=o.code, name=o.name, base_price=money(o.price), price=ZERO if free else money(o.price),
            free=free and o.price > 0, min_days=o.min_days, max_days=o.max_days,
        ))
    chosen = next((o for o in options if o.code == shipping_code), None) if shipping_code else None
    shipping_total = chosen.price if chosen else ZERO
    shipping_discount = (chosen.base_price - chosen.price) if chosen else ZERO

    thresholds = [o.free_over for o in available if o.free_over is not None and o.price > 0]
    threshold = min(thresholds) if thresholds else None
    remaining = None
    if threshold is not None and subtotal > 0 and not free_shipping_coupon:
        remaining = max(ZERO, money(threshold) - goods)

    # 4. Tax (on goods after discounts, plus shipping where a rate covers it)
    tax_lines: list[TaxLine] = []
    for rate in tax_rates:
        if not rate.matches(destination):
            continue
        base = goods + (shipping_total if rate.applies_to_shipping else ZERO)
        amount = percent_of(max(ZERO, base), rate.rate)
        tax_lines.append(TaxLine(name=rate.name, rate=rate.rate, amount=amount))
    tax_total = sum((t.amount for t in tax_lines), ZERO)

    total = goods + shipping_total + tax_total
    return Quote(
        currency=currency, lines=priced, list_subtotal=list_subtotal, subtotal=subtotal,
        sale_savings=list_subtotal - subtotal, coupon_code=applied_code, coupon_discount=coupon_discount,
        coupon_free_shipping=free_shipping_coupon, coupon_problem=problem, shipping_options=options,
        shipping_method=chosen.code if chosen else None, shipping_total=shipping_total,
        shipping_discount=shipping_discount, tax_lines=tax_lines, tax_total=tax_total, total=total,
        free_shipping_threshold=money(threshold) if threshold is not None else None, free_shipping_remaining=remaining,
    )
