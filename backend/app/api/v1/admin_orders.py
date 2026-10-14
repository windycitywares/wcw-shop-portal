"""Order management for staff: find, pay, ship, cancel, refund."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.common import Message
from app.schemas.orders import (
    CancelIn,
    MarkPaidIn,
    NoteIn,
    OrderAdminOut,
    OrderFilters,
    OrderListOut,
    RefundIn,
    ShipIn,
    StatusIn,
)
from app.services.orders import OrderService

router = APIRouter(prefix="/admin/orders", tags=["admin: orders"])
Staff = Annotated[User, Depends(require(Permission.ORDERS_MANAGE))]


def _filters(
    q: str | None = Query(None, max_length=100),
    status_: str | None = Query(None, alias="status", max_length=20),
    payment_status: str | None = Query(None, max_length=20),
    channel: str | None = Query(None, max_length=30),
    coupon: str | None = Query(None, max_length=40),
    start: date | None = None,
    end: date | None = None,
    needs_action: bool = False,
    sort: str = Query("newest", pattern="^(newest|oldest|total_desc|total_asc)$"),
    page: int = Query(1, ge=1, le=10_000),
    page_size: int = Query(25, ge=1, le=100),
) -> OrderFilters:
    return OrderFilters(
        q=q, status=status_, payment_status=payment_status, channel=channel, coupon=coupon, start=start, end=end,
        needs_action=needs_action, sort=sort, page=page, page_size=page_size,
    )


Filters = Annotated[OrderFilters, Depends(_filters)]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("", response_model=OrderListOut)
async def list_orders(response: Response, session: SessionDep, _: Staff, filters: Filters):
    _private(response)
    return await OrderService(session).search(filters)


@router.get("/export.csv")
async def export_orders(session: SessionDep, _: Staff, filters: Filters):
    """The orders matching the current filters (up to 5,000) as a CSV file."""
    data = await OrderService(session).export_csv(filters)
    return Response(
        data, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="wcw-orders.csv"', "Cache-Control": "no-store"},
    )


@router.get("/{order_id}", response_model=OrderAdminOut)
async def order_detail(order_id: int, response: Response, session: SessionDep, _: Staff):
    _private(response)
    return await OrderService(session).admin_detail(order_id)


@router.post("/{order_id}/mark-paid", response_model=OrderAdminOut)
async def mark_paid(order_id: int, session: SessionDep, user: Staff, data: MarkPaidIn):
    """Record a payment that arrived outside the card flow (bank transfer, cash, check)."""
    service = OrderService(session)
    await service.staff_mark_paid(order_id, data, user)
    return await service.admin_detail(order_id)


@router.post("/{order_id}/check-payment", response_model=OrderAdminOut)
async def check_payment(order_id: int, session: SessionDep, _: Staff):
    """Ask Stripe whether this card order has been paid."""
    service = OrderService(session)
    await service.check_payment(order_id)
    return await service.admin_detail(order_id)


@router.post("/{order_id}/status", response_model=OrderAdminOut)
async def change_status(order_id: int, session: SessionDep, user: Staff, data: StatusIn):
    service = OrderService(session)
    if data.status == "processing":
        await service.start_processing(order_id, user, data.note)
    else:
        await service.mark_delivered(order_id, user, data.note)
    return await service.admin_detail(order_id)


@router.post("/{order_id}/ship", response_model=OrderAdminOut)
async def ship_order(order_id: int, session: SessionDep, user: Staff, data: ShipIn):
    service = OrderService(session)
    await service.ship(order_id, data, user)
    return await service.admin_detail(order_id)


@router.post("/{order_id}/cancel", response_model=OrderAdminOut)
async def cancel_order(order_id: int, session: SessionDep, user: Staff, data: CancelIn):
    """Cancel an order that has not shipped. A paid order is refunded in full and its stock goes back on the shelf."""
    service = OrderService(session)
    await service.cancel(order_id, data, user)
    return await service.admin_detail(order_id)


@router.post("/{order_id}/refund", response_model=OrderAdminOut)
async def refund_order(order_id: int, session: SessionDep, user: Staff, data: RefundIn):
    service = OrderService(session)
    await service.refund(order_id, data, user)
    return await service.admin_detail(order_id)


@router.post("/{order_id}/note", response_model=OrderAdminOut, status_code=status.HTTP_201_CREATED)
async def add_note(order_id: int, session: SessionDep, user: Staff, data: NoteIn):
    """An internal note on the order's timeline (customers never see it)."""
    service = OrderService(session)
    await service.add_note(order_id, data.message, user)
    return await service.admin_detail(order_id)


@router.post("/{order_id}/resend", response_model=Message)
async def resend_confirmation(order_id: int, session: SessionDep, user: Staff):
    await OrderService(session).resend_confirmation(order_id, user)
    return Message(detail="Confirmation email sent")
