"""Loads the rules from the database and runs them through the pricing engine."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ContentStatus, StockStatus
from app.models.category import Category
from app.models.commerce import Coupon, ShippingMethod
from app.models.commerce import Sale as SaleRow
from app.models.commerce import TaxRate as TaxRow
from app.models.product import Product
from app.models.user import User
from app.pricing import engine
from app.pricing.codes import normalize_code
from app.repositories.commerce import CouponRepository, SaleRepository, ShippingRepository, TaxRepository
from app.repositories.order import OrderRepository
from app.schemas.order import MAX_QTY, CartItemIn
from app.schemas.product import ProductOut


# --- database rows -> engine objects ------------------------------------------------------------


def _scope(kind: str, category_id: int | None, product_ids: list[int], paths: dict[int, str]) -> engine.Scope:
    return engine.Scope(
        kind=kind,
        category_path=paths.get(category_id) if category_id else None,
        product_ids=frozenset(int(i) for i in product_ids or []),
    )


def to_sale(row: SaleRow, paths: dict[int, str]) -> engine.Sale:
    return engine.Sale(
        id=row.id, name=row.name, kind=row.kind, value=row.value, label=row.label, starts_at=row.starts_at,
        ends_at=row.ends_at, active=row.is_active, scope=_scope(row.scope, row.category_id, row.product_ids, paths),
    )


def to_coupon(row: Coupon, paths: dict[int, str]) -> engine.Coupon:
    return engine.Coupon(
        id=row.id, code=row.code, kind=row.kind, value=row.value, min_subtotal=row.min_subtotal,
        max_discount=row.max_discount, scope=_scope(row.scope, row.category_id, row.product_ids, paths),
        exclude_sale_items=row.exclude_sale_items, first_order_only=row.first_order_only, starts_at=row.starts_at,
        expires_at=row.expires_at, active=row.is_active, usage_limit=row.usage_limit, used_count=row.used_count,
        per_customer_limit=row.per_customer_limit, user_id=row.user_id, email=row.email,
    )


def to_shipping(row: ShippingMethod) -> engine.ShippingOption:
    return engine.ShippingOption(
        code=row.code, name=row.name, price=row.price, free_over=row.free_over, min_days=row.min_days,
        max_days=row.max_days, countries=frozenset(c.upper() for c in row.countries or []),
    )


def to_tax(row: TaxRow) -> engine.TaxRate:
    return engine.TaxRate(
        id=row.id, name=row.name, country=row.country, rate=row.rate, region=row.region,
        applies_to_shipping=row.applies_to_shipping,
    )


async def category_paths(session: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    wanted = {i for i in ids if i}
    if not wanted:
        return {}
    rows = await session.execute(select(Category.id, Category.path).where(Category.id.in_(wanted)))
    return {cid: path for cid, path in rows.all()}


# --- sale prices on the storefront --------------------------------------------------------------


async def apply_sales(session: AsyncSession, products: list[ProductOut], *, inherit_category: int | None = None) -> None:
    """Fill in `sale_price`, `sale_label` and `sale_ends_at` on products (and variants) that are on sale now.

    `inherit_category` is used for variants, which have no category of their own.
    """
    if not products:
        return
    now = datetime.now(timezone.utc)
    live = await SaleRepository(session).live(now)
    if not live:
        return
    paths = await category_paths(
        session, {p.category_id for p in products} | {inherit_category} | {s.category_id for s in live}
    )
    sales = [to_sale(s, paths) for s in live]
    ends = {s.id: s.ends_at for s in live}
    for p in products:
        category = p.category_id or inherit_category
        line = engine.Line(
            key=str(p.id), product_id=p.id, unit_price=p.base_price, quantity=1, parent_id=p.parent_id,
            category_path=paths.get(category) if category else None,
        )
        sale, price = engine.best_sale(line, sales, now)
        if sale is not None:
            p.sale_price = price
            p.sale_label = sale.label or sale.name
            p.sale_ends_at = ends.get(sale.id)


# --- the cart ------------------------------------------------------------------------------------


@dataclass
class ResolvedItem:
    product: Product
    parent: Product | None
    quantity: int
    category_id: int | None
    title: str
    attributes: dict

    @property
    def stock_limit(self) -> int | None:
        """How many can be bought, or None when there is no limit (untracked, backorder or pre-order)."""
        if self.product.stock_status != StockStatus.IN_STOCK:
            return None
        return self.product.stock_quantity


@dataclass
class Priced:
    quote: engine.Quote
    items: list[ResolvedItem]  # same order as quote.lines
    unavailable: list[int]
    coupon: Coupon | None
    shipping: list[ShippingMethod] = field(default_factory=list)
    issues: dict[int, int | None] = field(default_factory=dict)  # product id -> how many can be bought


def merge_items(items: list[CartItemIn]) -> list[CartItemIn]:
    merged: dict[int, int] = {}
    for item in items:
        merged[item.product_id] = min(MAX_QTY, merged.get(item.product_id, 0) + item.quantity)
    return [CartItemIn(product_id=pid, quantity=q) for pid, q in merged.items()]


def variant_title(parent: Product, variant: Product) -> str:
    detail = ", ".join(
        "/".join(str(x) for x in v) if isinstance(v, list) else str(v) for v in variant.attributes.values()
    )
    return f"{parent.title} ({detail})" if detail else f"{parent.title} ({variant.title})"


class CartPricer:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.coupons = CouponRepository(session)
        self.orders = OrderRepository(session)

    async def resolve(self, items: list[CartItemIn]) -> tuple[list[ResolvedItem], list[int]]:
        """Products that can be bought right now, and the ids of those that can't."""
        wanted = [i.product_id for i in items]
        rows = (await self.session.execute(select(Product).where(Product.id.in_(wanted)))).scalars().all()
        by_id = {p.id: p for p in rows}
        parent_ids = {p.parent_id for p in rows if p.parent_id}
        parents: dict[int, Product] = {}
        if parent_ids:
            parents = {p.id: p for p in (await self.session.execute(select(Product).where(Product.id.in_(parent_ids)))).scalars().all()}
        resolved: list[ResolvedItem] = []
        unavailable: list[int] = []
        for item in items:
            product = by_id.get(item.product_id)
            parent = parents.get(product.parent_id) if product and product.parent_id else None
            ok = (
                product is not None
                and product.status == ContentStatus.PUBLISHED
                and product.stock_status != StockStatus.OUT_OF_STOCK
                and (product.parent_id is None or (parent is not None and parent.status == ContentStatus.PUBLISHED))
            )
            if not ok:
                unavailable.append(item.product_id)
                continue
            resolved.append(ResolvedItem(
                product=product, parent=parent, quantity=item.quantity,
                category_id=(parent.category_id if parent else product.category_id),
                title=variant_title(parent, product) if parent else product.title,
                attributes=dict(product.attributes or {}),
            ))
        return resolved, unavailable

    async def price(
        self,
        items: list[CartItemIn],
        *,
        coupon_code: str | None = None,
        shipping_code: str | None = None,
        destination: engine.Destination = engine.Destination(),
        email: str | None = None,
        user: User | None = None,
        lock_coupon: bool = False,
    ) -> Priced:
        now = datetime.now(timezone.utc)
        items = merge_items(items)
        resolved, unavailable = await self.resolve(items)

        live_sales = await SaleRepository(self.session).live(now)
        coupon_row = None
        code = normalize_code(coupon_code or "")
        if code:
            coupon_row = await self.coupons.get_by_code(code, lock=lock_coupon)
        paths = await category_paths(
            self.session,
            {r.category_id for r in resolved} | {s.category_id for s in live_sales} | ({coupon_row.category_id} if coupon_row else set()),
        )

        lines = [
            engine.Line(
                key=str(r.product.id), product_id=r.product.id, unit_price=r.product.base_price, quantity=r.quantity,
                parent_id=r.product.parent_id, category_path=paths.get(r.category_id) if r.category_id else None,
            )
            for r in resolved
        ]

        shopper = engine.Shopper(user_id=user.id if user else None, email=email.strip().lower() if email else None)
        coupon = None
        if coupon_row is not None:
            coupon = to_coupon(coupon_row, paths)
            prior = 0
            if coupon_row.first_order_only and (shopper.user_id or shopper.email):
                prior = await self.orders.prior_orders(shopper.user_id, shopper.email or "")
            uses = 0
            if coupon_row.per_customer_limit is not None and (shopper.user_id or shopper.email):
                uses = await self.coupons.uses_by(coupon_row.id, shopper.user_id, shopper.email)
            shopper = engine.Shopper(user_id=shopper.user_id, email=shopper.email, prior_orders=prior, coupon_uses=uses)

        methods = await ShippingRepository(self.session).list_all(active_only=True)
        rates = await TaxRepository(self.session).list_all(active_only=True)

        quote = engine.price_cart(
            lines, sales=[to_sale(s, paths) for s in live_sales], coupon=coupon, shopper=shopper,
            shipping=[to_shipping(m) for m in methods], shipping_code=shipping_code, destination=destination,
            tax_rates=[to_tax(r) for r in rates], now=now,
        )
        if code and coupon_row is None:
            quote.coupon_problem = engine.Problem("invalid", "That code isn't valid.")

        issues = {
            r.product.id: r.stock_limit
            for r in resolved
            if r.stock_limit is not None and r.quantity > r.stock_limit
        }
        return Priced(quote=quote, items=resolved, unavailable=unavailable, coupon=coupon_row if quote.coupon_code else None,
                      shipping=methods, issues=issues)
