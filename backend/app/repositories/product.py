from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.orm import selectinload

from app.core.enums import ContentStatus, StockStatus
from app.models.category import Category
from app.models.product import Product
from app.repositories.base import BaseRepository
from app.repositories.paths import subtree_of
from app.utils.text import escape_like

SORTS = {
    "newest": (Product.published_at.desc().nulls_last(), Product.id.desc()),
    "price_asc": (Product.base_price.asc(), Product.id.desc()),
    "price_desc": (Product.base_price.desc(), Product.id.desc()),
    "title": (Product.title.asc(), Product.id.asc()),
    "updated": (Product.updated_at.desc(), Product.id.desc()),
}


@dataclass
class ProductQuery:
    q: str | None = None
    category_path: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    attributes: dict[str, list[str]] = field(default_factory=dict)
    statuses: list[ContentStatus] | None = field(default_factory=lambda: [ContentStatus.PUBLISHED])
    in_stock_only: bool = False
    include_variants: bool = False
    created_by_id: int | None = None
    source: str | None = None
    sort: str = "newest"
    page: int = 1
    page_size: int = 24


class ProductRepository(BaseRepository[Product]):
    model = Product

    def _filtered(self, f: ProductQuery) -> Select:
        stmt = select(Product)
        if not f.include_variants:
            stmt = stmt.where(Product.parent_id.is_(None))
        if f.statuses:
            stmt = stmt.where(Product.status.in_(f.statuses))
        if f.q:
            like = f"%{escape_like(f.q.strip())}%"
            stmt = stmt.where(
                or_(Product.title.ilike(like), Product.sku.ilike(like), Product.description.ilike(like))
            )
        if f.category_path:
            stmt = stmt.join(Category, Product.category_id == Category.id).where(
                subtree_of(Category.path, f.category_path)
            )
        if f.min_price is not None:
            stmt = stmt.where(Product.base_price >= f.min_price)
        if f.max_price is not None:
            stmt = stmt.where(Product.base_price <= f.max_price)
        if f.in_stock_only:
            stmt = stmt.where(Product.stock_status == StockStatus.IN_STOCK)
        if f.created_by_id is not None:
            stmt = stmt.where(Product.created_by_id == f.created_by_id)
        if f.source:
            stmt = stmt.where(Product.source == f.source)
        for key, values in f.attributes.items():
            # Match either a scalar value or membership in a list value; both use the GIN index.
            conds = []
            for v in values:
                conds += [Product.attributes.contains({key: v}), Product.attributes.contains({key: [v]})]
            if conds:
                stmt = stmt.where(or_(*conds))
        return stmt

    async def search(self, f: ProductQuery) -> tuple[list[Product], int]:
        stmt = self._filtered(f)
        total = (await self.session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        order = SORTS.get(f.sort, SORTS["newest"])
        rows = await self.session.execute(
            stmt.order_by(*order).offset((f.page - 1) * f.page_size).limit(f.page_size)
        )
        return list(rows.scalars().all()), total

    async def get_with_relations(self, **filters) -> Product | None:
        stmt = (
            select(Product)
            .filter_by(**filters)
            .options(selectinload(Product.variants), selectinload(Product.category))
            .execution_options(populate_existing=True)  # always fresh after writes
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def find_existing(self, source: str, source_ref: str | None, sku: str | None) -> Product | None:
        if source_ref:
            found = await self.get_by(source=source, source_ref=source_ref)
            if found:
                return found
        if sku:
            return await self.get_by(sku=sku)
        return None

    async def set_variant_status(self, parent_id: int, status: ContentStatus) -> None:
        await self.session.execute(
            Product.__table__.update()
            .where(Product.parent_id == parent_id)
            .values(status=status, updated_at=func.now())
        )

    async def facets(self, category_path: str | None) -> dict:
        params: dict = {}
        category_filter = ""
        if category_path:
            category_filter = (
                "AND p.category_id IN (SELECT id FROM categories "
                "WHERE path = :cpath OR path LIKE :cpath_like)"
            )
            params["cpath"] = category_path
            params["cpath_like"] = f"{category_path}.%"
        base_where = f"p.status = 'published' AND p.parent_id IS NULL {category_filter}"

        attr_rows = await self.session.execute(
            text(
                f"""
                SELECT e.key, v.value, count(*) AS n
                FROM products p
                CROSS JOIN LATERAL jsonb_each(p.attributes) AS e
                CROSS JOIN LATERAL (
                    SELECT jsonb_array_elements_text(e.value) AS value
                    WHERE jsonb_typeof(e.value) = 'array'
                    UNION ALL
                    SELECT e.value #>> '{{}}'
                    WHERE jsonb_typeof(e.value) IN ('string', 'number', 'boolean')
                ) AS v
                WHERE {base_where}
                GROUP BY e.key, v.value
                ORDER BY e.key, n DESC, v.value
                """
            ),
            params,
        )
        price_row = (
            await self.session.execute(
                text(f"SELECT min(base_price), max(base_price) FROM products p WHERE {base_where}"),
                params,
            )
        ).one()

        grouped: dict[str, list[dict]] = {}
        for key, value, n in attr_rows.all():
            grouped.setdefault(key, []).append({"value": value, "count": n})
        return {
            "price_min": price_row[0],
            "price_max": price_row[1],
            "attributes": [{"key": k, "values": v} for k, v in grouped.items()],
        }

    async def stats(self) -> dict[str, int]:
        rows = await self.session.execute(
            select(Product.status, func.count()).where(Product.parent_id.is_(None)).group_by(Product.status)
        )
        by_status = {s.value: n for s, n in rows.all()}
        low_stock = await self.count(
            Product.stock_quantity.is_not(None), Product.stock_quantity <= 3, Product.status == ContentStatus.PUBLISHED
        )
        return {**{s.value: by_status.get(s.value, 0) for s in ContentStatus}, "low_stock": low_stock}
