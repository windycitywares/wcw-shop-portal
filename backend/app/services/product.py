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
from app.schemas.product import Facets, ProductCreate, ProductDetail, ProductOut, ProductUpdate
from app.services.pricing import apply_sales

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
    async def search(self, query: ProductQuery) -> Page[ProductOut]:
        items, total = await self.repo.search(query)
        outs = [ProductOut.model_validate(p) for p in items]
        await apply_sales(self.session, outs)
        return Page[ProductOut](items=outs, total=total, page=query.page, page_size=query.page_size)

    async def category_path_for_slug(self, slug: str) -> str:
        category = await self.categories.get_by(slug=slug)
        if not category:
            raise NotFoundError("Category not found")
        return category.path

    async def facets(self, category_slug: str | None) -> Facets:
        path = await self.category_path_for_slug(category_slug) if category_slug else None
        return Facets.model_validate(await self.repo.facets(path))

    async def detail(self, *, viewer: User | None = None, **lookup) -> ProductDetail:
        product = await self.repo.get_with_relations(**lookup)
        staff = self.policy.can_view_unpublished(viewer)
        if not product or (not staff and product.status != ContentStatus.PUBLISHED):
            raise NotFoundError("Product not found")
        variants = [v for v in product.variants if staff or v.status == ContentStatus.PUBLISHED]
        breadcrumb = await self.categories.ancestors(product.category.path) if product.category else []
        main = ProductOut.model_validate(product)
        variant_outs = [ProductOut.model_validate(v) for v in variants]
        await apply_sales(self.session, [main, *variant_outs], inherit_category=product.category_id)
        return ProductDetail(
            **main.model_dump(),
            variants=variant_outs,
            category=CategoryOut.model_validate(product.category) if product.category else None,
            breadcrumb=[CategoryOut.model_validate(c) for c in breadcrumb],
        )

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
