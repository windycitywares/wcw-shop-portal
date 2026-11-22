"""External shops → Suppliers: the list listings, orders and supplier logins pick from."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import SessionDep, require
from app.core.config import get_settings
from app.core.permissions import Permission
from app.models.user import User
from app.services.suppliers import SupplierDirectory

router = APIRouter(prefix="/admin/suppliers", tags=["admin: suppliers"])
Team = Annotated[User, Depends(require(Permission.ETSY_MANAGE))]


class SupplierIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool = True


class SupplierPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_name: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None


def _out(s) -> dict[str, Any]:
    return {k: getattr(s, k) for k in ("id", "name", "contact_name", "email", "phone", "notes", "is_active")}


@router.get("/meta")
async def meta(response: Response, session: SessionDep, user: Team) -> dict[str, Any]:
    """Whether the CRM manages the list (then it's read-only here) and where to manage it."""
    response.headers["Cache-Control"] = "no-store"
    return {"managed_by_crm": await SupplierDirectory(session).managed_by_crm(),
            "crm_url": get_settings().crm_web_url.rstrip("/") + "/suppliers"}


@router.get("")
async def list_suppliers(response: Response, session: SessionDep, user: Team) -> list[dict[str, Any]]:
    response.headers["Cache-Control"] = "no-store"
    return await SupplierDirectory(session).list()


@router.post("", status_code=201)
async def create_supplier(body: SupplierIn, session: SessionDep, user: Team) -> dict[str, Any]:
    return _out(await SupplierDirectory(session).create(user, body.model_dump()))


@router.patch("/{supplier_id}")
async def update_supplier(supplier_id: int, body: SupplierPatch, session: SessionDep, user: Team) -> dict[str, Any]:
    return _out(await SupplierDirectory(session).update(user, supplier_id, body.model_dump(exclude_unset=True)))
