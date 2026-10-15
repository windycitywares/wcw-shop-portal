"""Stock requests from customers: "email me when it's back" and requests for combinations the shop doesn't sell."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.engagement import AdminStockRequestList, StockRequestNotifyIn
from app.services.engagement import StockAlertService

router = APIRouter(prefix="/admin/stock-requests", tags=["admin: stock requests"])
Staff = Annotated[User, Depends(require(Permission.CUSTOMERS_VIEW))]


@router.get("", response_model=AdminStockRequestList)
async def list_stock_requests(
    response: Response, session: SessionDep, _: Staff,
    status_: str = Query("waiting", alias="status", pattern="^(waiting|done|all)$"),
    kind: str | None = Query(None, pattern="^(restock|request)$"),
    q: str | None = Query(None, max_length=100), page: int = Query(1, ge=1, le=10_000), page_size: int = Query(25, ge=1, le=100),
):
    response.headers["Cache-Control"] = "no-store"
    return await StockAlertService(session).admin_list(status_, kind, q, page, page_size)


@router.post("/{request_id}/notify", status_code=status.HTTP_204_NO_CONTENT)
async def tell_customer(request_id: int, session: SessionDep, user: Staff, data: StockRequestNotifyIn):
    """Email the customer that it can be ordered now (back-in-stock requests are also emailed automatically)."""
    await StockAlertService(session).admin_notify(request_id, data.message, user)


@router.post("/{request_id}/close", status_code=status.HTTP_204_NO_CONTENT)
async def close_request(request_id: int, session: SessionDep, user: Staff):
    """Close without emailing (e.g. the combination won't be made)."""
    await StockAlertService(session).admin_close(request_id, user)
