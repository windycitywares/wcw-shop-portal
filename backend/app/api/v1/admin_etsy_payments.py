"""Supplier payments for Etsy orders: pending vs settled, per supplier, record/undo (Admin), export CSV or Excel."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.domain.timeutil import store_today
from app.models.user import User
from app.services.etsy_supplier_payments import SupplierPayments

router = APIRouter(prefix="/admin/etsy/supplier-payments", tags=["admin: etsy supplier payments"])
Team = Annotated[User, Depends(require(Permission.ETSY_MANAGE))]
Admin = Annotated[User, Depends(require(Permission.ETSY_PAYMENTS))]
State = Literal["pending", "settled", "cost_missing", "all"]


class SettleIn(BaseModel):
    order_ids: list[int] = Field(min_length=1, max_length=500)
    paid_on: date | None = None
    reference: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=300)
    amount: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)] | None = None


class UndoIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


@router.get("/overview")
async def overview(
    response: Response, session: SessionDep, user: Team,
    supplier: Annotated[str | None, Query(max_length=200)] = None,
    date_from: date | None = None, date_to: date | None = None,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return await SupplierPayments(session).overview(supplier, date_from, date_to)


@router.get("")
async def list_payments(
    response: Response, session: SessionDep, user: Team,
    state: State = "pending",
    supplier: Annotated[str | None, Query(max_length=200)] = None,
    date_from: date | None = None, date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    rows, total = await SupplierPayments(session).rows(state, supplier, date_from, date_to, page_size, (page - 1) * page_size)
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/export")
async def export(
    session: SessionDep, user: Team,
    format: Literal["csv", "xlsx"] = "csv",
    state: State = "pending",
    supplier: Annotated[str | None, Query(max_length=200)] = None,
    date_from: date | None = None, date_to: date | None = None,
) -> Response:
    service = SupplierPayments(session)
    rows, _ = await service.rows(state, supplier, date_from, date_to)
    name = f"supplier-payments-{state}-{store_today().isoformat()}"
    if format == "xlsx":
        from app.services.exporting import XLSX_MIME

        data, mime, ext = service.xlsx_bytes(rows, f"{state.title()} payments"), XLSX_MIME, "xlsx"
    else:
        data, mime, ext = service.csv_bytes(rows), "text/csv; charset=utf-8", "csv"
    return Response(data, media_type=mime, headers={
        "Content-Disposition": f'attachment; filename="{name}.{ext}"', "Cache-Control": "no-store"})


@router.post("/settle")
async def settle(body: SettleIn, session: SessionDep, user: Admin) -> dict[str, Any]:
    return await SupplierPayments(session).settle(
        user, body.order_ids, body.paid_on or store_today(), body.reference, body.note, body.amount)


@router.post("/{order_id}/undo")
async def undo(order_id: int, body: UndoIn, session: SessionDep, user: Admin) -> dict[str, bool]:
    await SupplierPayments(session).unsettle(user, order_id, body.reason)
    return {"ok": True}
