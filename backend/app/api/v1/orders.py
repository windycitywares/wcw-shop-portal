"""Orders: staff manage them; customers see their own (signed in, or with the link from their email)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import CurrentUser, OptionalUser, SessionDep, require
from app.api.v1.auth import no_store
from app.core.enums import OrderStatus
from app.core.permissions import Permission
from app.models.user import User
from app.repositories.order import OrderQuery
from app.schemas.common import Page
from app.schemas.order import CancelIn, NoteIn, OrderCounts, OrderListItem, OrderOut, RefundIn, ShipIn, StatusIn
from app.services.orders import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])
Staff = Annotated[User, Depends(require(Permission.ORDERS_MANAGE))]


@router.get("", response_model=Page[OrderListItem])
async def list_orders(
    session: SessionDep,
    _: Staff,
    q: str | None = Query(default=None, max_length=100),
    status: Annotated[list[OrderStatus] | None, Query()] = None,
    provider: str | None = Query(default=None, pattern=r"^(stripe|offline|test)$"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    query = OrderQuery(q=q, statuses=status, provider=provider, date_from=date_from, date_to=date_to, page=page, page_size=page_size)
    return await OrderService(session).search(query)


@router.get("/counts", response_model=OrderCounts)
async def order_counts(session: SessionDep, _: Staff):
    return OrderCounts(counts=await OrderService(session).counts())


@router.get("/{number}", response_model=OrderOut)
async def get_order(
    number: str, response: Response, session: SessionDep, user: OptionalUser,
    token: str | None = Query(default=None, max_length=100),
):
    no_store(response)
    return await OrderService(session).view(number, user=user, token=token)


@router.post("/{number}/status", response_model=OrderOut)
async def set_status(number: str, session: SessionDep, user: Staff, data: StatusIn):
    return await OrderService(session).set_status(number, data.status, user)


@router.post("/{number}/ship", response_model=OrderOut)
async def ship(number: str, session: SessionDep, user: Staff, data: ShipIn):
    return await OrderService(session).ship(number, data, user)


@router.post("/{number}/cancel", response_model=OrderOut)
async def cancel(number: str, session: SessionDep, user: Staff, data: CancelIn):
    return await OrderService(session).cancel(number, data, user)


@router.post("/{number}/refund", response_model=OrderOut)
async def refund(number: str, session: SessionDep, user: Staff, data: RefundIn):
    return await OrderService(session).refund(number, data, user)


@router.put("/{number}/note", response_model=OrderOut)
async def set_note(number: str, session: SessionDep, user: Staff, data: NoteIn):
    return await OrderService(session).set_note(number, data.internal_note, user)


my_orders_router = APIRouter(prefix="/account/orders", tags=["account"])


@my_orders_router.get("", response_model=Page[OrderListItem])
async def my_orders(
    response: Response, session: SessionDep, user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    no_store(response)
    return await OrderService(session).search(OrderQuery(user_id=user.id, page=page, page_size=page_size))
