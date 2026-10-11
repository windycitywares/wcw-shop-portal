"""Turns parsed rows from any importer into catalog products (create or update)."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ContentStatus, StockStatus
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.permissions import Permission, has_permission
from app.importers import (
    ImportedProduct,
    ImportedVariant,
    ImportFormatError,
    ParseResult,
    get_importer,
)
from app.models.product import Product
from app.models.user import User
from app.repositories.category import CategoryRepository
from app.repositories.product import ProductRepository
from app.schemas.imports import ImportPreview, ImportRowError, ImportSummary, PreviewRow
from app.services.category import CategoryService
from app.services.product import CatalogPolicy
from app.utils.text import slugify


@dataclass
class ImportOptions:
    category_id: int | None = None  # used when a row has no category of its own
    publish: bool = False  # publish immediately (publishers/admins only)
    update_existing: bool = True  # update products already imported / with the same SKU


def _stock_status(quantity: int | None, explicit: StockStatus | None) -> StockStatus:
    if explicit:
        return explicit
    if quantity is not None and quantity <= 0:
        return StockStatus.OUT_OF_STOCK
    return StockStatus.IN_STOCK


class ImportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.products = ProductRepository(session)
        self.categories = CategoryRepository(session)
        self.category_service = CategoryService(session)

    # -- parsing -------------------------------------------------------
    def parse(self, source: str, content: bytes, filename: str) -> ParseResult:
        importer = get_importer(source)
        if importer is None:
            raise NotFoundError(f"Unknown import source '{source}'")
        try:
            return importer.parse(content, filename)
        except ImportFormatError as exc:
            raise ValidationFailedError(str(exc)) from exc

    def preview(self, source: str, content: bytes, filename: str, limit: int = 50) -> ImportPreview:
        result = self.parse(source, content, filename)
        rows = [
            PreviewRow(
                row=p.row,
                sku=p.sku,
                title=p.title,
                price=float(p.price),
                quantity=p.quantity,
                images=len(p.images),
                variants=len(p.variants),
                category=" > ".join(p.category_path) if p.category_path else None,
                attributes=p.attributes,
            )
            for p in result.products[:limit]
        ]
        return ImportPreview(source=result.source, total=len(result.products), rows=rows, warnings=result.warnings)

    # -- importing -----------------------------------------------------
    async def run(
        self, source: str, content: bytes, filename: str, user: User, options: ImportOptions
    ) -> ImportSummary:
        if not has_permission(user.role, Permission.CATALOG_IMPORT):
            raise PermissionDeniedError("You don't have permission to import products")
        if options.publish and not has_permission(user.role, Permission.CATALOG_PUBLISH):
            raise PermissionDeniedError("Only publishers and admins can publish on import")
        if options.category_id and not await self.categories.get(options.category_id):
            raise NotFoundError("Category not found")

        result = self.parse(source, content, filename)
        summary = ImportSummary(source=result.source, warnings=result.warnings)

        for item in result.products:
            try:
                async with self.session.begin_nested():  # one bad row doesn't sink the batch
                    outcome = await self._import_one(item, result.source, user, options, summary)
                if outcome == "created":
                    summary.created += 1
                elif outcome == "updated":
                    summary.updated += 1
                else:
                    summary.skipped += 1
            except (PermissionDeniedError, NotFoundError, ValidationFailedError) as exc:
                summary.errors.append(ImportRowError(row=item.row, title=item.title, error=exc.message))
            except Exception as exc:  # noqa: BLE001 - report and continue
                summary.errors.append(ImportRowError(row=item.row, title=item.title, error=str(exc)[:300]))
        await self.session.commit()
        return summary

    async def _import_one(
        self, item: ImportedProduct, source: str, user: User, options: ImportOptions, summary: ImportSummary
    ) -> str:
        status = self._target_status(item.status, user, options)

        parent: Product | None = None
        if item.parent_sku:
            parent = await self.products.get_by(sku=item.parent_sku)
            if parent is None:
                raise ValidationFailedError(f"Parent SKU '{item.parent_sku}' not found")

        category_id = options.category_id
        if item.category_path:
            category = await self.category_service.ensure_path(item.category_path)
            category_id = category.id if category else category_id

        existing = await self.products.find_existing(source, item.source_ref, item.sku)
        if existing and not options.update_existing:
            return "skipped"

        fields = {
            "title": item.title[:300],
            "description": item.description,
            "base_price": item.price,
            "compare_at_price": item.compare_at_price,
            "currency": item.currency,
            "stock_quantity": item.quantity,
            "stock_status": _stock_status(item.quantity, item.stock_status),
            "images": [{"url": u, "alt": item.title[:300]} for u in item.images],
            "tags": item.tags,
            "attributes": item.attributes,
            "seo_title": item.seo_title,
            "seo_description": item.seo_description,
        }
        if category_id:
            fields["category_id"] = category_id

        if existing:
            CatalogPolicy.assert_can_edit(user, existing)
            for k, v in fields.items():
                setattr(existing, k, v)
            if parent:
                existing.parent_id = parent.id
            self._set_status(existing, status, keep_current=item.status is None and not options.publish)
            product, outcome = existing, "updated"
        else:
            sku = item.sku or await self._generate_sku(source, item)
            slug_base = f"{parent.slug}-{sku}" if parent else item.title
            product = Product(
                **fields,
                sku=sku[:100],
                slug=await self.products.unique_slug(slug_base),
                parent_id=parent.id if parent else None,
                source=source,
                source_ref=(item.source_ref or sku)[:255],
                created_by_id=user.id,
            )
            self._set_status(product, status, keep_current=False)
            self.products.add(product)
            outcome = "created"

        await self.session.flush()
        for variant in item.variants:
            await self._import_variant(variant, product, source, user)
            summary.variants += 1
        return outcome

    async def _import_variant(self, v: ImportedVariant, parent: Product, source: str, user: User) -> None:
        existing = await self.products.find_existing(source, v.source_ref, v.sku)
        title = v.title or f"{parent.title} – {', '.join(str(x) for x in v.attributes.values())}"
        fields = {
            "title": title[:300],
            "base_price": v.price if v.price is not None else parent.base_price,
            "stock_quantity": v.quantity,
            "stock_status": _stock_status(v.quantity, None),
            "attributes": v.attributes,
            "images": [{"url": u, "alt": title[:300]} for u in v.images],
            "category_id": parent.category_id,
            "parent_id": parent.id,
            "currency": parent.currency,
        }
        if existing:
            CatalogPolicy.assert_can_edit(user, existing)
            for k, val in fields.items():
                setattr(existing, k, val)
            existing.status = parent.status
            return
        sku = v.sku or f"{parent.sku}-{slugify('-'.join(str(x) for x in v.attributes.values()))}"
        variant = Product(
            **fields,
            sku=sku[:100],
            slug=await self.products.unique_slug(f"{parent.slug}-{sku}"),
            source=source,
            source_ref=(v.source_ref or sku)[:255],
            status=parent.status,
            published_at=parent.published_at,
            created_by_id=user.id,
        )
        self.products.add(variant)
        await self.session.flush()

    # -- helpers -------------------------------------------------------
    @staticmethod
    def _target_status(requested: ContentStatus | None, user: User, options: ImportOptions) -> ContentStatus:
        can_publish = has_permission(user.role, Permission.CATALOG_PUBLISH)
        if options.publish:
            return ContentStatus.PUBLISHED
        if requested in (ContentStatus.PUBLISHED, ContentStatus.ARCHIVED) and not can_publish:
            return ContentStatus.DRAFT  # authors' rows always land as drafts
        return requested or ContentStatus.DRAFT

    @staticmethod
    def _set_status(product: Product, status: ContentStatus, keep_current: bool) -> None:
        if keep_current and product.status is not None:
            return
        product.status = status
        if status == ContentStatus.PUBLISHED and product.published_at is None:
            product.published_at = datetime.now(timezone.utc)

    async def _generate_sku(self, source: str, item: ImportedProduct) -> str:
        base = f"{source[:3].upper()}-{slugify(item.title, 60).upper()}"
        candidate, n = base, 2
        while await self.products.get_by(sku=candidate):
            candidate, n = f"{base}-{n}", n + 1
        return candidate

