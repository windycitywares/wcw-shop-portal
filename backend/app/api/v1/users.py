from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import SessionDep, require
from app.core.enums import UserRole
from app.core.exceptions import NotFoundError
from app.core.permissions import Permission
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.common import Page
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.auth import UserService

router = APIRouter(prefix="/users", tags=["users (admin)"])
Admin = Annotated[User, Depends(require(Permission.USERS_MANAGE))]


@router.get("", response_model=Page[UserOut])
async def list_users(
    session: SessionDep,
    _: Admin,
    q: str | None = None,
    role: UserRole | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    items, total = await UserRepository(session).search(q, role, page, page_size)
    return Page[UserOut](items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(session: SessionDep, _: Admin, data: UserCreate):
    return await UserService(session).create(data)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(session: SessionDep, _: Admin, user_id: int):
    user = await UserRepository(session).get(user_id)
    if not user:
        raise NotFoundError("User not found")
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(session: SessionDep, admin: Admin, user_id: int, data: UserUpdate):
    return await UserService(session).update(user_id, data, acting=admin)
