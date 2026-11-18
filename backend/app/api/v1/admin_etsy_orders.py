"""Etsy orders for the team: list with filters, detail, costs/tracking entry and status changes (docs/ETSY.md)."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.domain import etsy_attention, etsy_status
from app.models.user import User
from app.services.etsy_order_admin import EtsyOrderAdmin

router = APIRouter(prefix="/admin/etsy/orders", tags=["admin: etsy orders"])
Team = Annotated[User, Depends(require(Permission.ETSY_MANAGE))]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class OrderPatchIn(BaseModel):
    purchase_cost: Money | None = None
    shipping_cost: Money | None = None
    supplier: str | None = Field(default=None, max_length=200)
    supplier_order_number: str | None = Field(default=None, max_length=100)
    carrier: str | None = Field(default=None, max_length=60)
    tracking_number: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=5000)
    buyer_phone: str | None = Field(default=None, max_length=50)


class StatusIn(BaseModel):
    status: str = Field(max_length=20)
    note: str | None = Field(default=None, max_length=300)


@router.get("/meta")
async def meta(user: Team) -> dict[str, Any]:
    """Status names and attention reasons, so the screens use the same words as the rules."""
    return {
        "statuses": [{"id": s, "label": etsy_status.LABELS[s], "main": s in etsy_status.MAIN_PATH} for s in etsy_status.ALL_STATUSES],
        "attention": etsy_attention.REASONS,
    }


@router.get("")
async def list_orders(
    response: Response, session: SessionDep, user: Team,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status: Annotated[str | None, Query(max_length=20)] = None,
    attention: bool = False,
    supplier: Annotated[str | None, Query(max_length=200)] = None,
    listing_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await EtsyOrderAdmin(session).search(
        q=q, status=status, attention=attention, supplier=supplier, listing_id=listing_id,
        date_from=date_from, date_to=date_to, page=page, page_size=page_size)


@router.get("/{order_id}")
async def get_order(order_id: int, response: Response, session: SessionDep, user: Team) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await EtsyOrderAdmin(session).detail(order_id)


@router.patch("/{order_id}")
async def update_order(order_id: int, body: OrderPatchIn, session: SessionDep, user: Team) -> dict[str, Any]:
    return await EtsyOrderAdmin(session).update(order_id, user, body.model_dump(exclude_unset=True))


@router.post("/{order_id}/status")
async def change_status(order_id: int, body: StatusIn, session: SessionDep, user: Team) -> dict[str, Any]:
    return await EtsyOrderAdmin(session).set_status(order_id, user, body.status, body.note)
