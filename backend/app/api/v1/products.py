from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.deps import CurrentUser, OptionalUser, SessionDep, require
from app.core.enums import ContentStatus
from app.core.exceptions import PermissionDeniedError
from app.core.permissions import Permission
from app.models.user import User
from app.repositories.product import SORTS, ProductQuery, ProductRepository
from app.schemas.common import Page
from app.schemas.product import (
    Facets,
    ProductCreate,
    ProductDetail,
    ProductOut,
    ProductUpdate,
    StatusChange,
)
from app.services.exporting import XLSX_MIME, ExportService
from app.services.product import CatalogPolicy, ProductService

router = APIRouter(prefix="/products", tags=["products"])
ATTR_PARAM_PREFIX = "attr."
Staff = Annotated[User, Depends(require(Permission.CATALOG_VIEW_UNPUBLISHED))]


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
    sort: Annotated[str, Query(pattern="^(" + "|".join(SORTS) + ")$")] = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
    status_filter: Annotated[list[ContentStatus] | None, Query(alias="status")] = None,
    mine: bool = False,
    source: str | None = None,
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
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return await service.search(query)


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


@router.get("/by-id/{product_id}", response_model=ProductDetail)
async def get_product_by_id(session: SessionDep, user: Staff, product_id: int):
    return await ProductService(session).detail(viewer=user, id=product_id)


@router.get("/{slug}", response_model=ProductDetail)
async def get_product(session: SessionDep, user: OptionalUser, slug: str):
    return await ProductService(session).detail(viewer=user, slug=slug)


@router.post("", response_model=ProductDetail, status_code=status.HTTP_201_CREATED)
async def create_product(
    session: SessionDep, user: Annotated[User, Depends(require(Permission.CATALOG_CREATE))], data: ProductCreate
):
    return await ProductService(session).create(data, user)


@router.patch("/{product_id}", response_model=ProductDetail)
async def update_product(session: SessionDep, user: CurrentUser, product_id: int, data: ProductUpdate):
    return await ProductService(session).update(product_id, data, user)


@router.post("/{product_id}/status", response_model=ProductDetail)
async def change_status(session: SessionDep, user: CurrentUser, product_id: int, data: StatusChange):
    """Workflow: draft -> in_review (authors) -> published / archived (publishers, admins)."""
    return await ProductService(session).set_status(product_id, data.status, user)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(session: SessionDep, user: CurrentUser, product_id: int):
    await ProductService(session).delete(product_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
