"""Abandoned carts: how many, how much money, and how many came back."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.domain.timeutil import resolve_range
from app.models.user import User
from app.schemas.carts import CartListOut
from app.services.carts import CartAdminService

router = APIRouter(prefix="/admin/carts", tags=["admin: carts"])
Staff = Annotated[User, Depends(require(Permission.CUSTOMERS_VIEW))]


@router.get("", response_model=CartListOut)
async def list_carts(
    response: Response, session: SessionDep, _: Staff,
    status_: str | None = Query(None, alias="status", pattern="^(active|abandoned|converted|recovered)$"),
    start: date | None = None, end: date | None = None, page: int = Query(1, ge=1, le=10_000), page_size: int = Query(25, ge=1, le=100),
):
    response.headers["Cache-Control"] = "no-store"
    rng = resolve_range(start, end, default_days=30)
    return await CartAdminService(session).list(status_, rng.start_utc, rng.end_utc, page, page_size)
