from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile, status

from app.api.deps import CurrentUser, OptionalUser, SessionDep, require
from app.core.enums import ContentStatus
from app.core.i18n import LANG_PATTERN
from app.core.config import get_settings
from app.core.exceptions import PermissionDeniedError, ValidationFailedError
from app.core.permissions import Permission
from app.models.user import User
from app.repositories.product import SORTS, ProductQuery, ProductRepository
from app.schemas.common import Page
from app.schemas.product import (
    Facets,
    ProductCard,
    ProductCreate,
    ProductDetail,
    ProductOut,
    ProductStaffDetail,
    ProductUpdate,
    StatusChange,
)
from app.services.exporting import XLSX_MIME, ExportService
from app.services import localize
from app.services.product import CatalogPolicy, ProductService

router = APIRouter(prefix="/products", tags=["products"])
ATTR_PARAM_PREFIX = "attr."
Staff = Annotated[User, Depends(require(Permission.CATALOG_VIEW_UNPUBLISHED))]
Lang = Annotated[str | None, Query(pattern=LANG_PATTERN, description="Language for titles and descriptions")]


def _attribute_filters(request: Request) -> dict[str, list[str]]:
    """?attr.Color=Red&attr.Color=Blue&attr.Material=Oak -> {"Color": ["Red","Blue"], ...}"""
    out: dict[str, list[str]] = {}
    for key, value in request.query_params.multi_items():
        if key.startswith(ATTR_PARAM_PREFIX) and value:
            out.setdefault(key[len(ATTR_PARAM_PREFIX) :], []).append(value)
    return out


@router.get("", response_model=Page[ProductOut])
async def list_products(
    request: Request,
    session: SessionDep,
    user: OptionalUser,
    q: str | None = None,
    category: Annotated[str | None, Query(description="Category slug; includes sub-categories")] = None,
    min_price: Annotated[Decimal | None, Query(ge=0)] = None,
    max_price: Annotated[Decimal | None, Query(ge=0)] = None,
    in_stock: bool = False,
    on_sale: bool = False,
    min_rating: Annotated[int | None, Query(ge=1, le=5)] = None,
    sort: Annotated[str, Query(pattern="^(" + "|".join(SORTS) + ")$")] = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    status_filter: Annotated[list[ContentStatus] | None, Query(alias="status")] = None,
    mine: bool = False,
    source: str | None = None,
    lang: Lang = None,
):
    """Storefront search with faceted filters. Use `attr.<Name>=<value>` for attributes.

    Staff can pass `status=draft&status=in_review` (or `mine=true`) to see unpublished items."""
    service = ProductService(session)
    staff = CatalogPolicy.can_view_unpublished(user)
    if (status_filter or mine) and not staff:
        raise PermissionDeniedError("Only staff can filter by status")
    query = ProductQuery(
        q=q,
        category_path=await service.category_path_for_slug(category) if category else None,
        min_price=min_price,
        max_price=max_price,
        attributes=_attribute_filters(request),
        statuses=status_filter if staff and status_filter else ([] if staff and mine else [ContentStatus.PUBLISHED]),
        in_stock_only=in_stock,
        created_by_id=user.id if mine and user else None,
        source=source,
        on_sale=await service.on_sale_clause() if on_sale else None,
        min_rating=min_rating,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    # Translations are left out of storefront lists (they'd triple the payload).
    return localize.page(await service.search(query, lang), lang)


@router.get("/suggest", response_model=list[ProductCard])
async def suggest_products(
    response: Response, session: SessionDep, q: Annotated[str, Query(min_length=2, max_length=80)], lang: Lang = None
):
    """Search-as-you-type: up to six matching products (title, price, photo)."""
    response.headers["Cache-Control"] = "public, max-age=30"
    return await ProductService(session).suggest(q, lang)


@router.get("/facets", response_model=Facets)
async def product_facets(session: SessionDep, category: str | None = None):
    """Available filter values (with counts) for published products, optionally within a category."""
    return await ProductService(session).facets(category)


@router.get("/stats")
async def product_stats(session: SessionDep, _: Staff):
    return await ProductRepository(session).stats()


@router.get("/export.xlsx")
async def export_products(session: SessionDep, _: Staff):
    """The whole catalog as an Excel file (same columns the spreadsheet importer reads)."""
    data = await ExportService(session).catalog_xlsx()
    return Response(
        data,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": 'attachment; filename="wcw-catalog.xlsx"'},
    )


@router.get("/by-id/{product_id}", response_model=ProductStaffDetail)
async def get_product_by_id(session: SessionDep, user: Staff, product_id: int):
    return await ProductService(session).detail(viewer=user, id=product_id)


@router.get("/{slug}/related", response_model=list[ProductCard])
async def related_products(response: Response, session: SessionDep, slug: str, lang: Lang = None):
    """"Customers also bought": products from the same paid orders, then popular ones from the category."""
    response.headers["Cache-Control"] = "public, max-age=120"
    return await ProductService(session).related(slug, lang)


@router.get("/{slug}", response_model=ProductDetail)
async def get_product(session: SessionDep, user: OptionalUser, slug: str, lang: Lang = None):
    result = await ProductService(session).detail(viewer=user, lang=lang, slug=slug)
    localize.product(result, lang)
    return result


@router.post("", response_model=ProductStaffDetail, status_code=status.HTTP_201_CREATED)
async def create_product(
    session: SessionDep, user: Annotated[User, Depends(require(Permission.CATALOG_CREATE))], data: ProductCreate
):
    return await ProductService(session).create(data, user)


@router.patch("/{product_id}", response_model=ProductStaffDetail)
async def update_product(session: SessionDep, user: CurrentUser, product_id: int, data: ProductUpdate):
    return await ProductService(session).update(product_id, data, user)


@router.get("/{product_id}/variant-template")
async def variant_template(session: SessionDep, user: Staff, product_id: int) -> dict:
    """Prefill for "Add variant": next SKU (parent SKU + "-<n>"), category, price, tags and option names."""
    return await ProductService(session).variant_template(product_id, user)


@router.post("/{product_id}/photos", response_model=ProductStaffDetail)
async def upload_photos(session: SessionDep, user: CurrentUser, product_id: int, files: Annotated[list[UploadFile], File()]):
    """Upload JPEG, PNG or WebP photos. They are re-encoded (metadata removed, very large ones scaled down), named after
    the product ("walnut-urn-1.jpg", "walnut-urn-2.jpg"…) and added after the existing photos."""
    limit = get_settings().max_photo_bytes
    if len(files) > 10:
        raise ValidationFailedError("Upload up to 10 photos at a time")
    data = []
    for f in files:
        raw = await f.read(limit + 1)
        if len(raw) > limit:
            raise ValidationFailedError(f"{f.filename or 'A photo'} is larger than {limit // (1024 * 1024)} MB")
        if raw:
            data.append(raw)
    return await ProductService(session).add_photos(product_id, data, user)


@router.delete("/{product_id}/photos", response_model=ProductStaffDetail)
async def remove_photo(session: SessionDep, user: CurrentUser, product_id: int, url: str = Query(max_length=2000)):
    return await ProductService(session).remove_photo(product_id, url, user)


@router.post("/{product_id}/status", response_model=ProductStaffDetail)
async def change_status(session: SessionDep, user: CurrentUser, product_id: int, data: StatusChange):
    """Workflow: draft -> in_review (authors) -> published / archived (publishers, admins)."""
    return await ProductService(session).set_status(product_id, data.status, user)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(session: SessionDep, user: CurrentUser, product_id: int):
    await ProductService(session).delete(product_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
