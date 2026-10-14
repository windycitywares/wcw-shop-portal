"""The pricing engine: sale prices, automatic cart rules, coupons, shipping and tax.

Pure functions over plain values. The API loads rules from the database and hands them here, so every
price the shopper sees (cart, checkout, emails) comes from exactly one place and is easy to test.

Order of operations (the same as Amazon's "item price -> promotions -> shipping -> tax"):

1. Sale price per product: the best active sale replaces the product's price.
2. One automatic cart rule: the satisfied rule that saves the most ("best offer applies").
3. One coupon code. It stacks on the rule only when the coupon is marked stackable, otherwise the
   customer simply gets whichever of the two saves more. Free-shipping offers never compete.
4. Shipping: flat rate, free over a threshold or when a free-shipping offer applies.
5. Tax on the discounted goods (and on shipping only where the settings say so).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.domain.money import ZERO, allocate, percent_of, q2

# ---------------------------------------------------------------------------------------------
# Scopes and products
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Scope:
    """Which cart lines an offer applies to."""

    kind: str = "order"  # order | category | products
    category_paths: tuple[str, ...] = ()  # materialized paths such as "1.4" (subtree match)
    product_ids: frozenset[int] = frozenset()
    exclude_sale_items: bool = False


@dataclass(frozen=True)
class ProductFacts:
    id: int
    base_price: Decimal
    parent_id: int | None = None
    category_path: str | None = None
    compare_at_price: Decimal | None = None


def in_category(path: str | None, category_paths: tuple[str, ...]) -> bool:
    if not path:
        return False
    return any(path == p or path.startswith(p + ".") for p in category_paths)


def _within(now: datetime, starts_at: datetime | None, ends_at: datetime | None) -> bool:
    return (starts_at is None or starts_at <= now) and (ends_at is None or now < ends_at)


# ---------------------------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SaleRule:
    id: int
    name: str
    kind: str  # percent | fixed
    value: Decimal
    scope: str = "all"  # all | category | products
    category_paths: tuple[str, ...] = ()
    product_ids: frozenset[int] = frozenset()
    exclude_product_ids: frozenset[int] = frozenset()
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    badge: str | None = None


@dataclass(frozen=True)
class SalePrice:
    sale: SaleRule
    price: Decimal  # what the shopper pays per unit
    list_price: Decimal  # the price before the sale (strike-through)

    @property
    def percent_off(self) -> int:
        if self.list_price <= 0:
            return 0
        return int(((self.list_price - self.price) / self.list_price * 100).to_integral_value())


def sale_applies(sale: SaleRule, product: ProductFacts, now: datetime) -> bool:
    if not sale.is_active or not _within(now, sale.starts_at, sale.ends_at):
        return False
    if product.id in sale.exclude_product_ids or (product.parent_id in sale.exclude_product_ids):
        return False
    if sale.scope == "all":
        return True
    if sale.scope == "category":
        return in_category(product.category_path, sale.category_paths)
    if sale.scope == "products":
        return product.id in sale.product_ids or (product.parent_id is not None and product.parent_id in sale.product_ids)
    return False


def discounted(price: Decimal, sale: SaleRule) -> Decimal:
    if sale.kind == "percent":
        return max(ZERO, q2(price - percent_of(price, sale.value)))
    return max(ZERO, q2(price - sale.value))


def best_sale(product: ProductFacts, sales: list[SaleRule], now: datetime) -> SalePrice | None:
    """The applicable sale with the lowest resulting price (ties: oldest sale). None if nothing saves money."""
    best: SalePrice | None = None
    for sale in sorted(sales, key=lambda s: s.id):
        if not sale_applies(sale, product, now):
            continue
        price = discounted(product.base_price, sale)
        if price >= product.base_price:
            continue
        if best is None or price < best.price:
            best = SalePrice(sale=sale, price=price, list_price=product.base_price)
    return best


# ---------------------------------------------------------------------------------------------
# Cart lines
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    product_id: int
    quantity: int
    unit_price: Decimal  # after any sale
    list_price: Decimal  # before any sale
    parent_id: int | None = None
    category_path: str | None = None
    sale_id: int | None = None

    @property
    def total(self) -> Decimal:
        return q2(self.unit_price * self.quantity)

    @property
    def on_sale(self) -> bool:
        return self.unit_price < self.list_price


def eligible(line: Line, scope: Scope) -> bool:
    if scope.exclude_sale_items and line.on_sale:
        return False
    if scope.kind == "category":
        return in_category(line.category_path, scope.category_paths)
    if scope.kind == "products":
        return line.product_id in scope.product_ids or (line.parent_id is not None and line.parent_id in scope.product_ids)
    return True


def _eligible_amount(lines: list[Line], scope: Scope, reduced_by: dict[int, Decimal] | None = None) -> Decimal:
    reduced_by = reduced_by or {}
    return sum((max(ZERO, l.total - reduced_by.get(i, ZERO)) for i, l in enumerate(lines) if eligible(l, scope)), ZERO)


def _spread(amount: Decimal, lines: list[Line], scope: Scope, reduced_by: dict[int, Decimal] | None = None) -> dict[int, Decimal]:
    """Split an order-level discount across the lines it applies to (largest remainder, exact to the cent)."""
    reduced_by = reduced_by or {}
    idx = [i for i, l in enumerate(lines) if eligible(l, scope)]
    weights = [max(ZERO, lines[i].total - reduced_by.get(i, ZERO)) for i in idx]
    return dict(zip(idx, allocate(amount, weights), strict=True))


# ---------------------------------------------------------------------------------------------
# Automatic cart rules
# ---------------------------------------------------------------------------------------------

RULE_KINDS = ("spend_percent", "spend_fixed", "qty_percent", "qty_fixed", "free_shipping")


@dataclass(frozen=True)
class CartRuleDef:
    id: int
    name: str
    kind: str
    value: Decimal = ZERO
    threshold_amount: Decimal | None = None
    threshold_qty: int | None = None
    max_discount: Decimal | None = None
    scope: Scope = field(default_factory=Scope)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    priority: int = 0


@dataclass(frozen=True)
class RuleResult:
    rule: CartRuleDef
    discount: Decimal  # 0 for free_shipping rules
    free_shipping: bool = False


def _rule_progress(rule: CartRuleDef, lines: list[Line]) -> tuple[Decimal, int]:
    amount = _eligible_amount(lines, rule.scope)
    qty = sum(l.quantity for l in lines if eligible(l, rule.scope))
    return amount, qty


def evaluate_rule(rule: CartRuleDef, lines: list[Line], now: datetime) -> RuleResult | None:
    """The saving this rule gives for the cart, or None when it is inactive or not yet satisfied."""
    if not rule.is_active or not _within(now, rule.starts_at, rule.ends_at):
        return None
    amount, qty = _rule_progress(rule, lines)
    if amount <= 0:
        return None
    if rule.kind == "free_shipping":
        if rule.threshold_amount is not None and amount < rule.threshold_amount:
            return None
        return RuleResult(rule, ZERO, free_shipping=True)
    if rule.kind.startswith("spend_"):
        if rule.threshold_amount is None or amount < rule.threshold_amount:
            return None
    elif rule.kind.startswith("qty_"):
        if rule.threshold_qty is None or qty < rule.threshold_qty:
            return None
    else:
        return None
    if rule.kind.endswith("_percent"):
        saving = percent_of(amount, rule.value)
    else:
        saving = min(q2(rule.value), amount)
    if rule.max_discount is not None:
        saving = min(saving, rule.max_discount)
    if saving <= 0:
        return None
    return RuleResult(rule, saving)


@dataclass(frozen=True)
class Reward:
    """A cart rule the shopper is close to: "spend $20 more and save 10%"."""

    rule: CartRuleDef
    remaining_amount: Decimal | None
    remaining_qty: int | None


def next_rewards(rules: list[CartRuleDef], lines: list[Line], now: datetime, limit: int = 2) -> list[Reward]:
    out: list[tuple[Decimal, Reward]] = []
    for rule in rules:
        if not rule.is_active or not _within(now, rule.starts_at, rule.ends_at):
            continue
        if evaluate_rule(rule, lines, now) is not None:
            continue
        amount, qty = _rule_progress(rule, lines)
        if amount <= 0:
            continue  # nothing in the cart this offer applies to, so don't suggest it
        if rule.kind in ("spend_percent", "spend_fixed") or (rule.kind == "free_shipping" and rule.threshold_amount):
            if rule.threshold_amount is None or amount >= rule.threshold_amount:
                continue
            remaining = rule.threshold_amount - amount
            out.append((remaining / rule.threshold_amount, Reward(rule, q2(remaining), None)))
        elif rule.kind in ("qty_percent", "qty_fixed") and rule.threshold_qty:
            if qty >= rule.threshold_qty:
                continue
            remaining_qty = rule.threshold_qty - qty
            out.append((Decimal(remaining_qty) / Decimal(rule.threshold_qty), Reward(rule, None, remaining_qty)))
    out.sort(key=lambda t: (t[0], t[1].rule.id))
    return [r for _, r in out[:limit]]


# ---------------------------------------------------------------------------------------------
# Coupons
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CouponDef:
    id: int
    code: str
    kind: str  # percent | fixed | free_shipping
    value: Decimal = ZERO
    max_discount: Decimal | None = None
    min_subtotal: Decimal = ZERO
    scope: Scope = field(default_factory=Scope)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    usage_limit: int | None = None
    used_count: int = 0
    per_customer_limit: int | None = None
    first_order_only: bool = False
    assigned_email: str | None = None
    stackable: bool = False
    is_active: bool = True


@dataclass(frozen=True)
class Customer:
    """What we know about the shopper when a coupon is checked."""

    email: str | None = None
    prior_orders: int = 0  # paid or open (not cancelled) orders before this one
    coupon_uses: int = 0  # times this shopper already used this coupon


def coupon_problem(coupon: CouponDef, lines: list[Line], customer: Customer, now: datetime) -> str | None:
    """Reason code why the coupon can't be used, or None when it can.

    Codes: inactive, not_started, expired, used_up, wrong_customer, needs_email, per_customer_limit,
    first_order_only, min_subtotal, no_eligible_items.
    """
    if not coupon.is_active:
        return "inactive"
    if coupon.starts_at and now < coupon.starts_at:
        return "not_started"
    if coupon.expires_at and now >= coupon.expires_at:
        return "expired"
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        return "used_up"
    email = (customer.email or "").strip().lower()
    if coupon.assigned_email:
        if not email:
            return "needs_email"
        if email != coupon.assigned_email.strip().lower():
            return "wrong_customer"
    if coupon.per_customer_limit is not None or coupon.first_order_only:
        if not email:
            return "needs_email"
        if coupon.per_customer_limit is not None and customer.coupon_uses >= coupon.per_customer_limit:
            return "per_customer_limit"
        if coupon.first_order_only and customer.prior_orders > 0:
            return "first_order_only"
    amount = _eligible_amount(lines, coupon.scope)
    if amount <= 0:
        return "no_eligible_items"
    if amount < coupon.min_subtotal:
        return "min_subtotal"
    return None


def coupon_saving(coupon: CouponDef, lines: list[Line], reduced_by: dict[int, Decimal] | None = None) -> Decimal:
    amount = _eligible_amount(lines, coupon.scope, reduced_by)
    if coupon.kind == "percent":
        saving = percent_of(amount, coupon.value)
    elif coupon.kind == "fixed":
        saving = min(q2(coupon.value), amount)
    else:
        return ZERO
    if coupon.max_discount is not None:
        saving = min(saving, coupon.max_discount)
    return max(ZERO, saving)


# ---------------------------------------------------------------------------------------------
# Shipping and tax
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ShippingConfig:
    flat_rate: Decimal = Decimal("8.95")
    free_threshold: Decimal | None = Decimal("100.00")
    domestic_country: str = "US"
    international_rate: Decimal | None = None  # None = domestic only
    allowed_countries: tuple[str, ...] = ("US",)


@dataclass(frozen=True)
class TaxConfig:
    enabled: bool = False
    rate_percent: Decimal = ZERO
    regions: tuple[str, ...] = ("IL",)  # states/regions where we collect tax
    country: str = "US"
    shipping_taxable: bool = False


@dataclass(frozen=True)
class Destination:
    country: str | None = None
    region: str | None = None  # state / province (2-letter code or full name)


US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD", "massachusetts": "MA",
    "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


def region_code(region: str | None) -> str:
    """'Illinois', 'illinois', ' il ' -> 'IL'. Unknown text is returned upper-cased."""
    if not region:
        return ""
    cleaned = region.strip()
    return US_STATES.get(cleaned.lower(), cleaned.upper())


@dataclass(frozen=True)
class ShippingResult:
    amount: Decimal
    free: bool
    reason: str  # flat | threshold | offer | international | none
    free_threshold: Decimal | None
    remaining_for_free: Decimal | None  # how much more goods to add for free shipping (None = n/a)
    deliverable: bool = True


def shipping_for(
    cfg: ShippingConfig, dest: Destination, goods_total: Decimal, free_offer: bool, has_items: bool = True
) -> ShippingResult:
    country = (dest.country or cfg.domestic_country).upper()
    if not has_items:
        return ShippingResult(ZERO, True, "none", cfg.free_threshold, None)
    if country != cfg.domestic_country.upper():
        if cfg.international_rate is None or country not in cfg.allowed_countries:
            return ShippingResult(ZERO, False, "international", None, None, deliverable=False)
        return ShippingResult(q2(cfg.international_rate), False, "international", None, None)
    if free_offer:
        return ShippingResult(ZERO, True, "offer", cfg.free_threshold, None)
    threshold = cfg.free_threshold
    if threshold is not None and goods_total >= threshold:
        return ShippingResult(ZERO, True, "threshold", threshold, None)
    remaining = q2(threshold - goods_total) if threshold is not None else None
    return ShippingResult(q2(cfg.flat_rate), False, "flat", threshold, remaining)


@dataclass(frozen=True)
class TaxResult:
    amount: Decimal
    rate_percent: Decimal
    estimated: bool  # True when the destination was unknown and the store's home region was assumed


def tax_for(cfg: TaxConfig, dest: Destination, goods_total: Decimal, shipping: Decimal) -> TaxResult | None:
    """Sales tax for the destination, or None when none is collected there."""
    if not cfg.enabled or cfg.rate_percent <= 0:
        return None
    country = (dest.country or cfg.country).upper()
    if country != cfg.country.upper():
        return None
    region = region_code(dest.region)
    if not region:
        return None
    if region not in {r.upper() for r in cfg.regions}:
        return None
    taxable = goods_total + (shipping if cfg.shipping_taxable else ZERO)
    return TaxResult(percent_of(max(ZERO, taxable), cfg.rate_percent), cfg.rate_percent, estimated=False)


# ---------------------------------------------------------------------------------------------
# The quote
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AppliedDiscount:
    type: str  # rule | coupon | free_shipping
    label: str
    amount: Decimal
    code: str | None = None
    id: int | None = None


@dataclass(frozen=True)
class CouponOutcome:
    code: str
    valid: bool
    applied: bool  # valid but beaten by a better automatic offer
    reason: str | None = None  # coupon_problem() code, or "better_offer"


@dataclass(frozen=True)
class Quote:
    lines: list[Line]
    line_discounts: list[Decimal]  # order-level discount share per line (same order as `lines`)
    subtotal: Decimal  # goods after sale prices
    list_subtotal: Decimal  # goods at list prices
    sale_savings: Decimal
    discounts: list[AppliedDiscount]
    discount_total: Decimal
    shipping: ShippingResult
    tax: TaxResult | None
    total: Decimal
    coupon: CouponOutcome | None
    rewards: list[Reward]

    @property
    def goods_after_discounts(self) -> Decimal:
        return self.subtotal - self.discount_total


def build_quote(
    lines: list[Line],
    *,
    now: datetime,
    rules: list[CartRuleDef],
    coupon: CouponDef | None,
    coupon_code: str | None,
    customer: Customer,
    shipping_cfg: ShippingConfig,
    tax_cfg: TaxConfig,
    destination: Destination,
) -> Quote:
    subtotal = sum((l.total for l in lines), ZERO)
    list_subtotal = sum((q2(l.list_price * l.quantity) for l in lines), ZERO)

    # -- automatic offers --------------------------------------------------------------------
    results = [r for r in (evaluate_rule(rule, lines, now) for rule in rules) if r is not None]
    discount_rules = sorted((r for r in results if not r.free_shipping and r.discount > 0),
                            key=lambda r: (-r.discount, -r.rule.priority, r.rule.id))
    best_rule = discount_rules[0] if discount_rules else None
    free_ship_rule = next((r for r in sorted(results, key=lambda r: (-r.rule.priority, r.rule.id)) if r.free_shipping), None)

    # -- coupon ------------------------------------------------------------------------------
    outcome: CouponOutcome | None = None
    coupon_ok = False
    if coupon_code:
        problem = coupon_problem(coupon, lines, customer, now) if coupon else "unknown"
        if coupon is None or problem:
            outcome = CouponOutcome(coupon_code, valid=False, applied=False, reason=problem or "unknown")
        else:
            outcome = CouponOutcome(coupon.code, valid=True, applied=True)
            coupon_ok = True

    applied: list[AppliedDiscount] = []
    reduced: dict[int, Decimal] = {}
    line_discounts = [ZERO] * len(lines)

    def add_share(shares: dict[int, Decimal]) -> None:
        for i, amt in shares.items():
            reduced[i] = reduced.get(i, ZERO) + amt
            line_discounts[i] += amt

    rule_applied = best_rule
    coupon_applied = coupon if coupon_ok else None
    coupon_free_ship = bool(coupon_applied and coupon_applied.kind == "free_shipping")

    if coupon_applied and not coupon_free_ship:
        coupon_value = coupon_saving(coupon_applied, lines)
        if best_rule is not None and not coupon_applied.stackable:
            if coupon_value > best_rule.discount:
                rule_applied = None  # the code beats the automatic offer
            else:
                coupon_applied = None  # the automatic offer is better, keep the code unused
                assert outcome is not None
                outcome = CouponOutcome(outcome.code, valid=True, applied=False, reason="better_offer")

    if rule_applied is not None:
        shares = _spread(rule_applied.discount, lines, rule_applied.rule.scope)
        add_share(shares)
        applied.append(AppliedDiscount("rule", rule_applied.rule.name, rule_applied.discount, id=rule_applied.rule.id))
    if coupon_applied is not None and not coupon_free_ship:
        saving = min(coupon_saving(coupon_applied, lines, reduced), subtotal - sum(reduced.values(), ZERO))
        if saving > 0:
            add_share(_spread(saving, lines, coupon_applied.scope, reduced))
            applied.append(AppliedDiscount("coupon", coupon_applied.code, saving, code=coupon_applied.code, id=coupon_applied.id))
        elif outcome is not None and outcome.applied:
            outcome = CouponOutcome(outcome.code, valid=True, applied=False, reason="no_eligible_items")

    discount_total = sum((d.amount for d in applied), ZERO)
    goods = subtotal - discount_total

    # -- shipping and tax --------------------------------------------------------------------
    free_offer = coupon_free_ship or free_ship_rule is not None
    shipping = shipping_for(shipping_cfg, destination, goods, free_offer, has_items=bool(lines))
    if coupon_free_ship and coupon_applied is not None and shipping.free and shipping.reason == "offer":
        applied.append(AppliedDiscount("free_shipping", coupon_applied.code, ZERO, code=coupon_applied.code, id=coupon_applied.id))
    elif free_ship_rule is not None and shipping.free and shipping.reason == "offer":
        applied.append(AppliedDiscount("free_shipping", free_ship_rule.rule.name, ZERO, id=free_ship_rule.rule.id))
    tax = tax_for(tax_cfg, destination, goods, shipping.amount)
    total = max(ZERO, goods + shipping.amount + (tax.amount if tax else ZERO))

    return Quote(
        lines=lines, line_discounts=line_discounts, subtotal=subtotal, list_subtotal=list_subtotal,
        sale_savings=list_subtotal - subtotal, discounts=applied, discount_total=discount_total,
        shipping=shipping, tax=tax, total=total, coupon=outcome,
        rewards=next_rewards(rules, lines, now),
    )
