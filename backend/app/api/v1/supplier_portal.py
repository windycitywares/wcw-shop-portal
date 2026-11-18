"""The supplier's own screens (role supplier): their orders on the shops they may see, shipping them, and what they're
owed. Everything is scoped to the signed-in supplier; see app/services/supplier_portal.py."""

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import SessionDep, require
from app.core.permissions import Permission
from app.domain.timeutil import store_today
from app.models.user import User
from app.schemas.user import UserOut
from app.services.etsy_supplier_payments import SupplierPayments
from app.services.supplier_accounts import SupplierAccounts
from app.services.supplier_portal import SupplierPortal

router = APIRouter(prefix="/supplier", tags=["supplier"])
Supplier = Annotated[User, Depends(require(Permission.SUPPLIER_PORTAL))]


class TrackingIn(BaseModel):
    supplier_order_number: str | None = Field(default=None, max_length=100)
    carrier: str | None = Field(default=None, max_length=60)
    tracking_number: str | None = Field(default=None, max_length=100)


class ShippedIn(BaseModel):
    carrier: str | None = Field(default=None, max_length=60)
    tracking_number: str = Field(min_length=1, max_length=100)


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.get("/me")
async def me(response: Response, session: SessionDep, user: Supplier) -> dict[str, Any]:
    _private(response)
    return await SupplierPortal(session, user).me()


@router.get("/etsy/orders")
async def orders(
    response: Response, session: SessionDep, user: Supplier,
    view: Literal["to_ship", "shipped", "all"] = "to_ship",
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    _private(response)
    return await SupplierPortal(session, user).orders(view, q, page, page_size)


@router.get("/etsy/orders/{order_id}")
async def order(order_id: int, response: Response, session: SessionDep, user: Supplier) -> dict[str, Any]:
    _private(response)
    return await SupplierPortal(session, user).detail(order_id)


@router.patch("/etsy/orders/{order_id}")
async def update_order(order_id: int, body: TrackingIn, session: SessionDep, user: Supplier) -> dict[str, Any]:
    return await SupplierPortal(session, user).update(order_id, body.model_dump(exclude_unset=True))


@router.post("/etsy/orders/{order_id}/shipped")
async def shipped(order_id: int, body: ShippedIn, session: SessionDep, user: Supplier) -> dict[str, Any]:
    return await SupplierPortal(session, user).mark_shipped(order_id, body.carrier, body.tracking_number)


@router.get("/etsy/payments")
async def payments(
    response: Response, session: SessionDep, user: Supplier,
    state: Literal["pending", "settled", "all"] = "pending",
    date_from: date | None = None, date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    _private(response)
    name = await SupplierPortal(session, user).payments_filter()
    service = SupplierPayments(session)
    overview = await service.overview(name, date_from, date_to)
    rows, total = await service.rows(state, name, date_from, date_to, page_size, (page - 1) * page_size)
    keep = ("id", "etsy_receipt_id", "ordered_at", "supplier_order_number", "items", "owed", "payment_status",
            "paid_at", "paid_amount", "payment_ref")
    return {
        "pending_count": overview["pending_count"], "pending_amount": overview["pending_amount"],
        "settled_count": overview["settled_count"], "settled_amount": overview["settled_amount"],
        "items": [{k: r[k] for k in keep} for r in rows], "total": total, "page": page, "page_size": page_size,
    }


@router.get("/etsy/payments/export")
async def export_payments(
    session: SessionDep, user: Supplier,
    format: Literal["csv", "xlsx"] = "csv",
    state: Literal["pending", "settled", "all"] = "all",
    date_from: date | None = None, date_to: date | None = None,
) -> Response:
    name = await SupplierPortal(session, user).payments_filter()
    service = SupplierPayments(session)
    rows, _ = await service.rows(state, name, date_from, date_to)
    filename = f"payments-{state}-{store_today().isoformat()}"
    if format == "xlsx":
        from app.services.exporting import XLSX_MIME

        data, mime, ext = service.xlsx_bytes(rows, "Payments"), XLSX_MIME, "xlsx"
    else:
        data, mime, ext = service.csv_bytes(rows), "text/csv; charset=utf-8", "csv"
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="{filename}.{ext}"', "Cache-Control": "no-store"})


# ---- admins: supplier logins ------------------------------------------------------------------------------------

admin_router = APIRouter(prefix="/admin/supplier-logins", tags=["admin: supplier logins"])
Admin = Annotated[User, Depends(require(Permission.USERS_MANAGE))]


class SupplierLoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = Field(default=None, max_length=200)
    supplier_name: str = Field(min_length=1, max_length=200)
    channels: list[str] = Field(min_length=1, max_length=10)


class SupplierLoginPatch(BaseModel):
    supplier_name: str | None = Field(default=None, min_length=1, max_length=200)
    channels: list[str] | None = Field(default=None, min_length=1, max_length=10)


@admin_router.get("", response_model=list[UserOut])
async def list_logins(session: SessionDep, _: Admin):
    return await SupplierAccounts(session).list()


@admin_router.post("", response_model=UserOut, status_code=201)
async def create_login(body: SupplierLoginIn, session: SessionDep, admin: Admin):
    return await SupplierAccounts(session).create(
        admin, email=body.email, password=body.password, full_name=body.full_name,
        supplier_name=body.supplier_name, channels=body.channels)


@admin_router.patch("/{user_id}", response_model=UserOut)
async def update_login(user_id: int, body: SupplierLoginPatch, session: SessionDep, admin: Admin):
    return await SupplierAccounts(session).update(admin, user_id, supplier_name=body.supplier_name, channels=body.channels)
