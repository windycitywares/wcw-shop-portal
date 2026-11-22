"""Suppliers between the CRM and the shop (docs/CRM_SYNC.md → "Suppliers"). The CRM owns the supplier list: it sends each
supplier it adds or changes here, and reads a supplier's order figures for its supplier page. Same bearer token as the
rest of /integrations/crm; always live data."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import SessionDep
from app.api.v1.crm_read import Token
from app.models.supplier import Supplier
from app.services.suppliers import SupplierDirectory

router = APIRouter(prefix="/integrations/crm/suppliers", tags=["integrations"], include_in_schema=False)


class CrmSupplierIn(BaseModel):
    crm_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    is_active: bool = True
    contact_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)


@router.get("", dependencies=[Token])
async def list_suppliers(session: SessionDep) -> dict[str, Any]:
    """Every shop supplier, for the CRM's first import (names the shop already uses become CRM suppliers)."""
    rows = (await session.execute(select(Supplier).order_by(Supplier.id))).scalars().all()
    return {"items": [{"id": s.id, "name": s.name, "crm_id": s.crm_id, "is_active": s.is_active, "contact_name": s.contact_name,
                       "email": s.email, "phone": s.phone, "notes": s.notes} for s in rows]}


@router.post("", dependencies=[Token])
async def receive_supplier(body: CrmSupplierIn, session: SessionDep) -> dict[str, Any]:
    s, outcome = await SupplierDirectory(session).from_crm(body.model_dump())
    return {"result": outcome, "id": s.id, "name": s.name}


@router.get("/stats", dependencies=[Token])
async def supplier_stats(session: SessionDep, name: str = Query(min_length=1, max_length=200)) -> dict[str, Any]:
    return await SupplierDirectory(session).stats(name)
