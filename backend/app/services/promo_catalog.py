"""Active sales, automatic offers and category paths, loaded once and shared for a few seconds.

Everything that shows or charges a price goes through here, so a product card, the product page, the
cart and checkout always agree.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import ColumnElement, and_, false, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ContentStatus, StockStatus
from app.core.i18n import DEFAULT_LANGUAGE
from app.domain.pricing import CartRuleDef, ProductFacts, SaleRule, Scope, best_sale, in_category
from app.models.category import Category
from app.models.commerce import CartRule, Sale
from app.models.product import Product
from app.schemas.product import ProductOut
from app.services.ttl import TtlCache

NEW_PRODUCT_DAYS = 30
BEST_SELLER_MIN_UNITS = 3
BEST_SELLER_COUNT = 12


@dataclass
class PromoCatalog:
    sales: list[SaleRule] = field(default_factory=list)
    sale_names: dict[int, dict[str, str]] = field(default_factory=dict)  # sale id -> {lang: label}
    rules: list[CartRuleDef] = field(default_factory=list)
    rule_names: dict[int, dict[str, str]] = field(default_factory=dict)
    category_paths: dict[int, str] = field(default_factory=dict)
    category_ids_by_path: dict[str, int] = field(default_factory=dict)
    best_sellers: frozenset[int] = frozenset()

    def sale_label(self, sale_id: int, lang: str | None) -> str:
        names = self.sale_names.get(sale_id, {})
        return names.get(lang or DEFAULT_LANGUAGE) or names.get(DEFAULT_LANGUAGE, "")

    def rule_label(self, rule_id: int, lang: str | None) -> str:
        names = self.rule_names.get(rule_id, {})
        return names.get(lang or DEFAULT_LANGUAGE) or names.get(DEFAULT_LANGUAGE, "")

    def path_for(self, category_id: int | None, parent_category_id: int | None = None) -> str | None:
        if category_id is not None and category_id in self.category_paths:
            return self.category_paths[category_id]
        if parent_category_id is not None:
            return self.category_paths.get(parent_category_id)
        return None


def _paths_for(ids: Iterable[int], category_paths: dict[int, str]) -> tuple[str, ...]:
    return tuple(category_paths[i] for i in ids if i in category_paths)


def sale_rule(row: Sale, category_paths: dict[int, str]) -> SaleRule:
    return SaleRule(
        id=row.id, name=row.name, kind=row.kind, value=row.value, scope=row.scope,
        category_paths=_paths_for(row.category_ids or [], category_paths),
        product_ids=frozenset(row.product_ids or []), exclude_product_ids=frozenset(row.exclude_product_ids or []),
        starts_at=row.starts_at, ends_at=row.ends_at, is_active=row.is_active, badge=row.badge,
    )


def rule_def(row: CartRule, category_paths: dict[int, str]) -> CartRuleDef:
    return CartRuleDef(
        id=row.id, name=row.name, kind=row.kind, value=row.value, threshold_amount=row.threshold_amount,
        threshold_qty=row.threshold_qty, max_discount=row.max_discount,
        scope=Scope(row.scope, _paths_for(row.category_ids or [], category_paths), frozenset(row.product_ids or []), row.exclude_sale_items),
        starts_at=row.starts_at, ends_at=row.ends_at, is_active=row.is_active, priority=row.priority,
    )


def _labels(base: str, translations: dict, keys: tuple[str, ...]) -> dict[str, str]:
    out = {DEFAULT_LANGUAGE: base}
    for lang, fields_ in (translations or {}).items():
        for key in keys:
            if isinstance(fields_, dict) and fields_.get(key):
                out[lang] = fields_[key]
                break
    return out


_cache: TtlCache[PromoCatalog] = TtlCache(ttl=20)


def clear_cache() -> None:
    _cache.clear()


async def load(session: AsyncSession, now: datetime | None = None) -> PromoCatalog:
    cached = _cache.get()
    if cached is not None:
        return cached
    now = now or datetime.now(timezone.utc)
    window_start, window_end = now - timedelta(hours=2), now + timedelta(hours=36)

    cats = (await session.execute(select(Category.id, Category.path))).all()
    category_paths = {cid: path for cid, path in cats}

    def overlaps(row) -> bool:  # keep rows whose window touches [now-2h, now+36h]; exact windows are re-checked per call
        return (row.starts_at is None or row.starts_at <= window_end) and (row.ends_at is None or row.ends_at >= window_start)

    sale_rows = [r for r in (await session.execute(select(Sale).where(Sale.is_active.is_(True)))).scalars().all() if overlaps(r)]
    rule_rows = [r for r in (await session.execute(select(CartRule).where(CartRule.is_active.is_(True)))).scalars().all() if overlaps(r)]
    sellers = (
        await session.execute(
            select(Product.id)
            .where(Product.status == ContentStatus.PUBLISHED, Product.parent_id.is_(None), Product.units_sold >= BEST_SELLER_MIN_UNITS)
            .order_by(Product.units_sold.desc(), Product.id)
            .limit(BEST_SELLER_COUNT)
        )
    ).scalars().all()

    catalog = PromoCatalog(
        sales=[sale_rule(r, category_paths) for r in sale_rows],
        sale_names={r.id: _labels(r.badge or r.name, r.translations, ("badge", "name")) for r in sale_rows},
        rules=[rule_def(r, category_paths) for r in rule_rows],
        rule_names={r.id: _labels(r.name, r.translations, ("name",)) for r in rule_rows},
        category_paths=category_paths,
        category_ids_by_path={path: cid for cid, path in category_paths.items()},
        best_sellers=frozenset(sellers),
    )
    return _cache.set(catalog)


def facts(product: Product | ProductOut, promo: PromoCatalog, parent_category_id: int | None = None) -> ProductFacts:
    return ProductFacts(
        id=product.id, base_price=product.base_price, parent_id=product.parent_id,
        category_path=promo.path_for(product.category_id, parent_category_id),
        compare_at_price=product.compare_at_price,
    )


def decorate(
    outs: Iterable[ProductOut], promo: PromoCatalog, lang: str | None, low_stock_threshold: int,
    now: datetime | None = None, parent_category_id: int | None = None,
) -> None:
    """Fill in sale price, label, countdown and badges on product outputs (in place)."""
    now = now or datetime.now(timezone.utc)
    for out in outs:
        found = best_sale(facts(out, promo, parent_category_id), promo.sales, now)
        badges: list[str] = []
        if found:
            out.sale_price = found.price
            out.sale_label = promo.sale_label(found.sale.id, lang) or None
            out.sale_ends_at = found.sale.ends_at
            badges.append("sale")
        else:
            out.sale_price = out.sale_label = out.sale_ends_at = None
        if out.id in promo.best_sellers:
            badges.append("best_seller")
        if out.published_at and now - out.published_at <= timedelta(days=NEW_PRODUCT_DAYS):
            badges.append("new")
        if (
            out.stock_quantity is not None and 0 < out.stock_quantity <= low_stock_threshold
            and out.stock_status == StockStatus.IN_STOCK
        ):
            badges.append("low_stock")
        out.badges = badges


def on_sale_clause(promo: PromoCatalog, now: datetime | None = None) -> ColumnElement[bool]:
    """SQL condition for "has an active sale" (mirrors domain.pricing.sale_applies)."""
    now = now or datetime.now(timezone.utc)
    conditions: list[ColumnElement[bool]] = []
    for sale in promo.sales:
        if not sale.is_active or (sale.starts_at and sale.starts_at > now) or (sale.ends_at and sale.ends_at <= now):
            continue
        if sale.scope == "all":
            cond: ColumnElement[bool] = true()
        elif sale.scope == "category":
            ids = [cid for cid, path in promo.category_paths.items() if in_category(path, sale.category_paths)]
            cond = Product.category_id.in_(ids) if ids else false()
        else:
            ids = list(sale.product_ids)
            cond = or_(Product.id.in_(ids), Product.parent_id.in_(ids)) if ids else false()
        if sale.exclude_product_ids:
            excluded = list(sale.exclude_product_ids)
            cond = and_(cond, Product.id.notin_(excluded), or_(Product.parent_id.is_(None), Product.parent_id.notin_(excluded)))
        conditions.append(cond)
    return or_(*conditions) if conditions else false()
