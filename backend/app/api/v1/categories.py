from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import OptionalUser, SessionDep, require
from app.core.i18n import LANG_PATTERN
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.category import (
    CategoryCreate,
    CategoryDetail,
    CategoryNode,
    CategoryOut,
    CategoryReorder,
    CategoryUpdate,
)
from app.services import localize
from app.services.category import CategoryService
from app.services.product import CatalogPolicy

router = APIRouter(prefix="/categories", tags=["categories"])
Manager = Annotated[User, Depends(require(Permission.CATEGORY_MANAGE))]
Lang = Annotated[str | None, Query(pattern=LANG_PATTERN, description="Language for names and descriptions")]


@router.get("/tree", response_model=list[CategoryNode])
async def category_tree(
    session: SessionDep, user: OptionalUser, include_inactive: bool = False, lang: Lang = None
):
    """Nested tree for the mega-menu (staff may include hidden categories).

    With `include_inactive` (the admin view) each node keeps its `translations` for editing."""
    staff_view = include_inactive and CatalogPolicy.can_view_unpublished(user)
    tree = await CategoryService(session).tree(active_only=not staff_view)
    for node in tree:
        localize.category(node, lang, keep=staff_view)
    return tree


@router.get("/{slug}", response_model=CategoryDetail)
async def category_detail(session: SessionDep, slug: str, lang: Lang = None):
    result = await CategoryService(session).detail_by_slug(slug)
    localize.category(result, lang)
    return result


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(session: SessionDep, _: Manager, data: CategoryCreate):
    return await CategoryService(session).create(data)


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(session: SessionDep, _: Manager, category_id: int, data: CategoryUpdate):
    return await CategoryService(session).update(category_id, data)


@router.post("/reorder", response_model=list[CategoryNode])
async def reorder_categories(session: SessionDep, _: Manager, data: CategoryReorder):
    """Save a drag-and-drop result from the admin tree."""
    return await CategoryService(session).reorder(data)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(session: SessionDep, _: Manager, category_id: int):
    await CategoryService(session).delete(category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
