from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import OptionalUser, SessionDep, require
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
from app.services.category import CategoryService
from app.services.product import CatalogPolicy

router = APIRouter(prefix="/categories", tags=["categories"])
Manager = Annotated[User, Depends(require(Permission.CATEGORY_MANAGE))]


@router.get("/tree", response_model=list[CategoryNode])
async def category_tree(session: SessionDep, user: OptionalUser, include_inactive: bool = False):
    """Nested tree for the mega-menu (staff may include hidden categories)."""
    active_only = not (include_inactive and CatalogPolicy.can_view_unpublished(user))
    return await CategoryService(session).tree(active_only=active_only)


@router.get("/{slug}", response_model=CategoryDetail)
async def category_detail(session: SessionDep, slug: str):
    return await CategoryService(session).detail_by_slug(slug)


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
