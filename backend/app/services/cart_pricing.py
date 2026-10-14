"""Prices a cart from the database.

One code path for the cart page, checkout, the order that gets saved and the abandoned-cart snapshot,
so the shopper never sees one price and pays another. The arithmetic itself lives in `domain/pricing.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ContentStatus, OrderStatus, StockStatus
from app.domain import coupons as coupon_codes
from app.domain.pricing import (
    CouponDef,
    Customer,
    Destination,
    Line,
    Quote,
    SalePrice,
    Scope,
    best_sale,
    build_quote,
)
from app.models.commerce import Coupon, CouponRedemption
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.schemas.product import ProductOut
from app.schemas.settings import StoreSettings
from app.schemas.shop import (
    CartItemIn,
    CouponStatusOut,
    DestinationIn,
    DiscountOut,
    QuoteLineOut,
    QuoteOut,
    RewardOut,
    ShippingOut,
    TaxOut,
)
from app.services import localize, promo_catalog
from app.services.messages import t
from app.services.promo_catalog import PromoCatalog, facts
from app.services.settings import SettingsService, shipping_config, tax_config


@dataclass
class PricedLine:
    product: Product
    parent: Product | None
    quantity: int
    options: dict[str, str]
    sale: SalePrice | None


@dataclass
class PricedCart:
    quote: Quote
    lines: list[PricedLine]  # same order as quote.lines
    messages: list[str]
    blocking: bool
    coupon_row: Coupon | None
    settings: StoreSettings
    promo: PromoCatalog
    destination: Destination
    email: str | None
    lang: str
    removed: list[int] = field(default_factory=list)


def variant_label(product: Product) -> str | None:
    """The option a variant stands for ("10 inch Large"), from its attributes or the part of its title after the dash."""
    if product.parent_id is None:
        return None
    for value in (product.attributes or {}).values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return product.title.split(" — ", 1)[1].strip() if " — " in product.title else None


def tracked_stock(product: Product) -> int | None:
    """Units we can promise, or None when stock is not limited (untracked, back-order and pre-order)."""
    if product.stock_status == StockStatus.IN_STOCK and product.stock_quantity is not None:
        return max(0, product.stock_quantity)
    return None


def purchasable(product: Product) -> bool:
    if product.stock_status == StockStatus.OUT_OF_STOCK:
        return False
    stock = tracked_stock(product)
    return stock is None or stock > 0


def _scope_of(row: Coupon, promo: PromoCatalog) -> Scope:
    return Scope(
        kind=row.scope,
        category_paths=tuple(promo.category_paths[i] for i in (row.category_ids or []) if i in promo.category_paths),
        product_ids=frozenset(row.product_ids or []),
        exclude_sale_items=row.exclude_sale_items,
    )


def coupon_def(row: Coupon, promo: PromoCatalog) -> CouponDef:
    return CouponDef(
        id=row.id, code=row.code, kind=row.kind, value=row.value, max_discount=row.max_discount,
        min_subtotal=row.min_subtotal, scope=_scope_of(row, promo), starts_at=row.starts_at, expires_at=row.expires_at,
        usage_limit=row.usage_limit, used_count=row.used_count, per_customer_limit=row.per_customer_limit,
        first_order_only=row.first_order_only, assigned_email=row.assigned_email, stackable=row.stackable,
        is_active=row.is_active,
    )


def _merge(items: list[CartItemIn]) -> list[tuple[int, dict[str, str], int]]:
    """Same product with the same options becomes one line (quantities add up)."""
    merged: dict[tuple, list] = {}
    for item in items:
        key = (item.product_id, tuple(sorted(item.options.items())))
        if key in merged:
            merged[key][2] += item.quantity
        else:
            merged[key] = [item.product_id, dict(item.options), item.quantity]
    return [(pid, opts, qty) for pid, opts, qty in merged.values()]


def _valid_options(product: Product, parent: Product | None, options: dict[str, str]) -> dict[str, str]:
    """Keep only choices the product really offers (list-valued attributes), so odd text can't end up on an order."""
    offered = {**((parent.attributes if parent else None) or {}), **(product.attributes or {})}
    out: dict[str, str] = {}
    for key, value in options.items():
        allowed = offered.get(key)
        if isinstance(allowed, list) and value in [str(a) for a in allowed]:
            out[key] = value
    return out


class CartPricer:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def customer_context(self, email: str | None, coupon: Coupon | None) -> Customer:
        if not email:
            return Customer()
        prior = (
            await self.session.execute(
                select(func.count()).select_from(Order).where(Order.email == email, Order.status != OrderStatus.CANCELLED)
            )
        ).scalar_one()
        uses = 0
        if coupon is not None:
            uses = (
                await self.session.execute(
                    select(func.count()).select_from(CouponRedemption).where(
                        CouponRedemption.coupon_id == coupon.id, CouponRedemption.email == email
                    )
                )
            ).scalar_one()
        return Customer(email=email, prior_orders=prior, coupon_uses=uses)

    async def price(
        self,
        items: list[CartItemIn],
        *,
        coupon_code: str | None = None,
        email: str | None = None,
        destination: DestinationIn | None = None,
        lang: str | None = "en",
        user: User | None = None,
        now: datetime | None = None,
    ) -> PricedCart:
        now = now or datetime.now(timezone.utc)
        lang = lang or "en"
        settings = await SettingsService(self.session).load()
        promo = await promo_catalog.load(self.session, now)
        messages: list[str] = []
        blocking = False

        merged = _merge(items)
        ids = {pid for pid, _, _ in merged}
        products: dict[int, Product] = {}
        if ids:
            rows = (await self.session.execute(select(Product).where(Product.id.in_(ids)))).scalars().all()
            products = {p.id: p for p in rows}
        parent_ids = {p.parent_id for p in products.values() if p.parent_id}
        parents: dict[int, Product] = {}
        if parent_ids:
            rows = (await self.session.execute(select(Product).where(Product.id.in_(parent_ids)))).scalars().all()
            parents = {p.id: p for p in rows}
        direct_parents = {p.id for p in products.values() if p.parent_id is None}
        with_variants: set[int] = set()
        if direct_parents:
            counted = (
                await self.session.execute(
                    select(Product.parent_id).where(
                        Product.parent_id.in_(direct_parents), Product.status == ContentStatus.PUBLISHED
                    ).distinct()
                )
            ).scalars().all()
            with_variants = set(counted)

        max_qty = settings.general.max_quantity_per_line
        lines: list[Line] = []
        info: list[PricedLine] = []
        removed: list[int] = []
        for pid, options, qty in merged:
            product = products.get(pid)
            parent = parents.get(product.parent_id) if product and product.parent_id else None
            if product is None or product.status != ContentStatus.PUBLISHED or (
                product.parent_id is not None and (parent is None or parent.status != ContentStatus.PUBLISHED)
            ):
                messages.append(t("line.unavailable", lang, title=localized_title(product, parent, lang)) if product
                                else t("line.unavailable_unknown", lang))
                removed.append(pid)
                blocking = True
                continue
            title = localized_title(product, parent, lang)
            if product.id in with_variants:
                messages.append(t("line.choose_option", lang, title=title))
                removed.append(pid)
                blocking = True
                continue
            if not purchasable(product):
                messages.append(t("line.out_of_stock", lang, title=title))
                removed.append(pid)
                blocking = True
                continue
            stock = tracked_stock(product)
            if stock is not None and qty > stock:
                messages.append(t("line.reduced", lang, n=stock, title=title))
                qty, blocking = stock, True
            if qty > max_qty:
                messages.append(t("line.max", lang, n=max_qty, title=title))
                qty, blocking = max_qty, True
            parent_category = parent.category_id if parent else None
            sale = best_sale(facts(product, promo, parent_category), promo.sales, now)
            unit = sale.price if sale else product.base_price
            lines.append(Line(
                product_id=product.id, quantity=qty, unit_price=unit, list_price=product.base_price,
                parent_id=product.parent_id, category_path=promo.path_for(product.category_id, parent_category),
                sale_id=sale.sale.id if sale else None,
            ))
            info.append(PricedLine(product, parent, qty, _valid_options(product, parent, options), sale))

        code = coupon_codes.normalize_code(coupon_code) or None
        coupon_row: Coupon | None = None
        if code:
            coupon_row = (await self.session.execute(select(Coupon).where(Coupon.code == code))).scalar_one_or_none()
        customer_email = (email or (user.email if user else None) or "").strip().lower() or None
        customer = await self.customer_context(customer_email, coupon_row)

        dest = Destination(country=destination.country if destination else None, region=destination.region if destination else None)
        quote = build_quote(
            lines, now=now, rules=promo.rules,
            coupon=coupon_def(coupon_row, promo) if coupon_row else None, coupon_code=code,
            customer=customer, shipping_cfg=shipping_config(settings), tax_cfg=tax_config(settings), destination=dest,
        )
        if not quote.shipping.deliverable:
            messages.append(t("shipping.undeliverable", lang))
        applied_row = coupon_row if quote.coupon and quote.coupon.valid and quote.coupon.applied else None
        return PricedCart(
            quote=quote, lines=info, messages=messages, blocking=blocking, coupon_row=applied_row,
            settings=settings, promo=promo, destination=dest, email=customer_email, lang=lang, removed=removed,
        )


def localized_title(product: Product | None, parent: Product | None, lang: str) -> str:
    if product is None:
        return ""
    source = parent or product
    out = ProductOut.model_validate(source)
    localize.product(out, lang)
    return out.title


def to_out(priced: PricedCart) -> QuoteOut:
    """The quote as the storefront receives it (texts in the shopper's language)."""
    quote, promo, settings, lang = priced.quote, priced.promo, priced.settings, priced.lang
    threshold = settings.general.low_stock_threshold
    out_lines: list[QuoteLineOut] = []
    for line, extra, share in zip(quote.lines, priced.lines, quote.line_discounts, strict=True):
        product, parent = extra.product, extra.parent
        stock = tracked_stock(product)
        image_source = product if product.images else parent
        images = (image_source.images if image_source else None) or []
        out_lines.append(QuoteLineOut(
            product_id=product.id, parent_id=product.parent_id, slug=(parent or product).slug, sku=product.sku,
            title=localized_title(product, parent, lang), variant=variant_label(product),
            image=images[0].get("url") if images else None, options=extra.options, quantity=line.quantity,
            unit_price=line.unit_price, list_price=line.list_price, line_total=line.total, line_discount=share,
            on_sale=line.on_sale, sale_label=(promo.sale_label(line.sale_id, lang) or None) if line.sale_id else None,
            stock_left=stock if stock is not None and 0 < stock <= threshold else None,
        ))
    discounts = []
    for d in quote.discounts:
        label = d.label
        if d.type in ("rule", "free_shipping") and d.id is not None and not d.code:
            label = promo.rule_label(d.id, lang) or d.label
        discounts.append(DiscountOut(type=d.type, label=label, amount=d.amount, code=d.code))
    tax = None
    if quote.tax is not None:
        tax = TaxOut(label=settings.tax.label, rate_percent=quote.tax.rate_percent, amount=quote.tax.amount)
    tax_pending = settings.tax.enabled and settings.tax.rate_percent > 0 and quote.tax is None and not priced.destination.region
    coupon = None
    if quote.coupon is not None:
        c = quote.coupon
        coupon = CouponStatusOut(
            code=c.code, valid=c.valid, applied=c.applied, reason=c.reason,
            message=t(f"coupon.{c.reason}", lang) if c.reason else None,
        )
    rewards = [
        RewardOut(
            name=promo.rule_label(r.rule.id, lang) or r.rule.name, kind=r.rule.kind, value=r.rule.value,
            remaining_amount=r.remaining_amount, remaining_qty=r.remaining_qty,
        )
        for r in quote.rewards
    ]
    shipping = quote.shipping
    return QuoteOut(
        lines=out_lines, item_count=sum(l.quantity for l in quote.lines), subtotal=quote.subtotal,
        list_subtotal=quote.list_subtotal, sale_savings=quote.sale_savings, discounts=discounts,
        discount_total=quote.discount_total,
        shipping=ShippingOut(
            amount=shipping.amount, free=shipping.free, reason=shipping.reason, free_threshold=shipping.free_threshold,
            remaining_for_free=shipping.remaining_for_free, deliverable=shipping.deliverable,
        ),
        tax=tax, tax_pending=tax_pending, total=quote.total, coupon=coupon, rewards=rewards, messages=priced.messages,
        blocking=priced.blocking,
    )
