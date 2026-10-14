from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ContentStatus
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.permissions import Permission, has_permission
from app.models.product import Product
from app.models.user import User
from app.repositories.category import CategoryRepository
from app.repositories.product import ProductQuery, ProductRepository
from app.schemas.category import CategoryOut
from app.schemas.common import Page
from app.schemas.product import (
    Facets,
    ProductCard,
    ProductCreate,
    ProductDetail,
    ProductOut,
    ProductStaffDetail,
    ProductUpdate,
)
from app.services import localize, promo_catalog
from app.services.settings import SettingsService

PUBLISHING_STATUSES = {ContentStatus.PUBLISHED, ContentStatus.ARCHIVED}


class CatalogPolicy:
    """Who may do what with a product. Pure functions, easy to test and extend."""

    @staticmethod
    def can_view_unpublished(user: User | None) -> bool:
        return bool(user) and has_permission(user.role, Permission.CATALOG_VIEW_UNPUBLISHED)

    @staticmethod
    def assert_can_set_status(user: User, status: ContentStatus) -> None:
        if status in PUBLISHING_STATUSES and not has_permission(user.role, Permission.CATALOG_PUBLISH):
            raise PermissionDeniedError("Only publishers and admins can publish or archive products")

    @staticmethod
    def assert_can_edit(user: User, product: Product) -> None:
        if has_permission(user.role, Permission.CATALOG_EDIT_ANY):
            return
        if (
            has_permission(user.role, Permission.CATALOG_EDIT_OWN)
            and product.created_by_id == user.id
            and product.status not in PUBLISHING_STATUSES
        ):
            return
        raise PermissionDeniedError("You can only edit your own unpublished products")


class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ProductRepository(session)
        self.categories = CategoryRepository(session)
        self.policy = CatalogPolicy()

    # -- reading -------------------------------------------------------
    async def decorate(self, outs: list[ProductOut], lang: str | None, parent_category_id: int | None = None) -> None:
        """Add sale prices, countdowns and badges (see services/promo_catalog)."""
        promo = await promo_catalog.load(self.session)
        threshold = (await SettingsService(self.session).load()).general.low_stock_threshold
        promo_catalog.decorate(outs, promo, lang, threshold, parent_category_id=parent_category_id)

    async def on_sale_clause(self):
        return promo_catalog.on_sale_clause(await promo_catalog.load(self.session))

    async def search(self, query: ProductQuery, lang: str | None = None) -> Page[ProductOut]:
        items, total = await self.repo.search(query)
        outs = [ProductOut.model_validate(p) for p in items]
        await self.decorate(outs, lang)
        return Page[ProductOut](items=outs, total=total, page=query.page, page_size=query.page_size)

    async def suggest(self, q: str, lang: str | None, limit: int = 6) -> list[ProductCard]:
        outs = [ProductOut.model_validate(p) for p in await self.repo.suggest(q, limit)]
        await self.decorate(outs, lang)
        return [self._card(o, lang) for o in outs]

    async def related(self, slug: str, lang: str | None, limit: int = 8) -> list[ProductCard]:
        """"Customers also bought": products from the same paid orders, topped up with popular ones from the category."""
        product = await self.repo.get_by(slug=slug)
        if not product or product.status != ContentStatus.PUBLISHED:
            raise NotFoundError("Product not found")
        root_id = product.parent_id or product.id
        ids = await self.repo.co_purchased_ids(root_id, limit)
        found = await self.repo.get_many(ids)
        if len(found) < limit:
            category_id = product.category_id
            if category_id is None and product.parent_id:
                parent = await self.repo.get(product.parent_id)
                category_id = parent.category_id if parent else None
            have = [root_id, *[p.id for p in found]]
            found += await self.repo.popular_in_category(category_id, have, limit - len(found))
        outs = [ProductOut.model_validate(p) for p in found]
        await self.decorate(outs, lang)
        return [self._card(o, lang) for o in outs]

    @staticmethod
    def _card(out: ProductOut, lang: str | None) -> ProductCard:
        localize.product(out, lang)
        image = out.images[0].url if out.images else None
        return ProductCard(
            id=out.id, slug=out.slug, title=out.title, base_price=out.base_price, sale_price=out.sale_price,
            compare_at_price=out.compare_at_price, image=image,
        )

    async def category_path_for_slug(self, slug: str) -> str:
        category = await self.categories.get_by(slug=slug)
        if not category:
            raise NotFoundError("Category not found")
        return category.path

    async def facets(self, category_slug: str | None) -> Facets:
        path = await self.category_path_for_slug(category_slug) if category_slug else None
        return Facets.model_validate(await self.repo.facets(path))

    async def detail(self, *, viewer: User | None = None, lang: str | None = None, **lookup) -> ProductStaffDetail | ProductDetail:
        product = await self.repo.get_with_relations(**lookup)
        staff = self.policy.can_view_unpublished(viewer)
        if not product or (not staff and product.status != ContentStatus.PUBLISHED):
            raise NotFoundError("Product not found")
        variants = [v for v in product.variants if staff or v.status == ContentStatus.PUBLISHED]
        breadcrumb = await self.categories.ancestors(product.category.path) if product.category else []
        extra = {"cost_price": product.cost_price, "units_sold": product.units_sold} if staff else {}
        cls = ProductStaffDetail if staff else ProductDetail
        result = cls(
            **ProductOut.model_validate(product).model_dump(),
            variants=[ProductOut.model_validate(v) for v in variants],
            category=CategoryOut.model_validate(product.category) if product.category else None,
            breadcrumb=[CategoryOut.model_validate(c) for c in breadcrumb],
            **extra,
        )
        await self.decorate([result], lang)
        await self.decorate(result.variants, lang, parent_category_id=product.category_id)
        return result

    # -- writing -------------------------------------------------------
    async def create(self, data: ProductCreate, user: User) -> ProductDetail:
        self.policy.assert_can_set_status(user, data.status)
        if await self.repo.get_by(sku=data.sku):
            raise ConflictError(f"SKU '{data.sku}' already exists")
        if data.category_id and not await self.categories.get(data.category_id):
            raise NotFoundError("Category not found")
        parent = None
        if data.parent_id:
            parent = await self.repo.get(data.parent_id)
            if not parent or parent.parent_id is not None:
                raise NotFoundError("Parent product not found (variants can't have variants)")
            self.policy.assert_can_edit(user, parent)

        if data.slug:
            if await self.repo.get_by(slug=data.slug):
                raise ConflictError(f"Slug '{data.slug}' is already used")
            slug = data.slug
        else:
            base = f"{parent.slug}-{data.sku}" if parent else data.title
            slug = await self.repo.unique_slug(base)

        payload = data.model_dump(exclude={"slug", "images"})
        product = Product(
            **payload,
            slug=slug,
            images=[i.model_dump() for i in data.images],
            created_by_id=user.id,
            source="manual",
        )
        if product.status == ContentStatus.PUBLISHED:
            product.published_at = datetime.now(timezone.utc)
        self.repo.add(product)
        await self.session.flush()
        new_id = product.id
        await self._commit()
        return await self.detail(viewer=user, id=new_id)

    async def update(self, product_id: int, data: ProductUpdate, user: User) -> ProductDetail:
        product = await self._get_or_404(product_id)
        self.policy.assert_can_edit(user, product)
        changes = data.model_dump(exclude_unset=True)

        if "status" in changes:
            if changes["status"] is None:
                changes.pop("status")
            else:
                self.policy.assert_can_set_status(user, changes["status"])
        if changes.get("sku") and changes["sku"] != product.sku and await self.repo.get_by(sku=changes["sku"]):
            raise ConflictError(f"SKU '{changes['sku']}' already exists")
        if changes.get("slug") and changes["slug"] != product.slug and await self.repo.get_by(slug=changes["slug"]):
            raise ConflictError(f"Slug '{changes['slug']}' is already used")
        if changes.get("category_id") and not await self.categories.get(changes["category_id"]):
            raise NotFoundError("Category not found")
        if "images" in changes and changes["images"] is not None:
            changes["images"] = [dict(i) for i in changes["images"]]

        required = {"title", "sku", "slug", "base_price", "currency", "stock_status", "attributes", "images", "tags", "translations"}
        for field, value in changes.items():
            if value is None and field in required:
                continue
            setattr(product, field, value)

        if "status" in changes:
            await self._apply_status_side_effects(product)
        await self._commit()
        return await self.detail(viewer=user, id=product_id)

    async def set_status(self, product_id: int, status: ContentStatus, user: User) -> ProductDetail:
        product = await self._get_or_404(product_id)
        self.policy.assert_can_edit(user, product)
        self.policy.assert_can_set_status(user, status)
        product.status = status
        await self._apply_status_side_effects(product)
        await self._commit()
        return await self.detail(viewer=user, id=product_id)

    async def delete(self, product_id: int, user: User) -> None:
        product = await self._get_or_404(product_id)
        if not has_permission(user.role, Permission.CATALOG_DELETE):
            # Authors may discard their own drafts
            self.policy.assert_can_edit(user, product)
        await self.repo.delete(product)
        await self._commit()

    # -- helpers -------------------------------------------------------
    async def _apply_status_side_effects(self, product: Product) -> None:
        if product.status == ContentStatus.PUBLISHED and product.published_at is None:
            product.published_at = datetime.now(timezone.utc)
        if product.parent_id is None:
            await self.session.flush()
            await self.repo.set_variant_status(product.id, product.status)

    async def _get_or_404(self, product_id: int) -> Product:
        product = await self.repo.get(product_id)
        if not product:
            raise NotFoundError("Product not found")
        return product

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ConflictError("That change conflicts with an existing product (duplicate SKU or slug?)") from exc
