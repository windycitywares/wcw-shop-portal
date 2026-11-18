"""The supplier list: who the shop buys from. Listings, orders and supplier logins pick a supplier from it (they keep its
name); renaming a supplier renames it everywhere. Suppliers are switched off, never deleted, so history stays."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.domain import etsy_status
from app.models.etsy import EtsyListing, EtsyOrder
from app.models.supplier import Supplier
from app.models.user import User
from app.services import audit

FIELDS = ("name", "contact_name", "email", "phone", "notes", "is_active")


def _clean_name(value: str) -> str:
    name = " ".join((value or "").split())
    if not name:
        raise ValidationFailedError("Enter the supplier's name")
    return name[:200]


class SupplierDirectory:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_name(self, name: str) -> Supplier | None:
        return (await self.session.execute(
            select(Supplier).where(func.lower(Supplier.name) == name.strip().lower()))).scalar_one_or_none()

    async def resolve(self, name: str | None) -> str | None:
        """The listed supplier's exact name for a picked value; None clears it. Unknown names are refused."""
        if name is None or not name.strip():
            return None
        found = await self.by_name(" ".join(name.split()))
        if found is None:
            raise ValidationFailedError(f"“{name.strip()}” isn't in your supplier list. Add it under External shops → Suppliers first.")
        if not found.is_active:
            raise ValidationFailedError(f"{found.name} is switched off in your supplier list")
        return found.name

    async def list(self) -> list[dict[str, Any]]:
        rows = (await self.session.execute(select(Supplier).order_by(Supplier.is_active.desc(), func.lower(Supplier.name)))).scalars().all()
        key = func.lower(EtsyOrder.supplier)
        listings = dict((await self.session.execute(
            select(func.lower(EtsyListing.internal_supplier), func.count()).where(EtsyListing.internal_supplier.is_not(None))
            .group_by(func.lower(EtsyListing.internal_supplier)))).all())
        open_orders = dict((await self.session.execute(
            select(key, func.count()).where(EtsyOrder.supplier.is_not(None), EtsyOrder.status.in_(etsy_status.OPEN_STATUSES))
            .group_by(key))).all())
        owed = dict((await self.session.execute(
            select(key, func.sum(EtsyOrder.purchase_cost + func.coalesce(EtsyOrder.shipping_cost, 0)))
            .where(EtsyOrder.supplier.is_not(None), EtsyOrder.supplier_paid_at.is_(None), EtsyOrder.purchase_cost.is_not(None),
                   EtsyOrder.status != "cancelled").group_by(key))).all())
        logins = dict((await self.session.execute(
            select(func.lower(User.supplier_name), func.count()).where(User.role == UserRole.SUPPLIER, User.is_active.is_(True))
            .group_by(func.lower(User.supplier_name)))).all())
        out = []
        for s in rows:
            k = s.name.lower()
            out.append({
                "id": s.id, "name": s.name, "contact_name": s.contact_name, "email": s.email, "phone": s.phone,
                "notes": s.notes, "is_active": s.is_active, "listings": listings.get(k, 0), "open_orders": open_orders.get(k, 0),
                "owed": Decimal(owed.get(k) or 0).quantize(Decimal("0.01")), "logins": logins.get(k, 0),
            })
        return out

    async def create(self, actor: User, data: dict[str, Any]) -> Supplier:
        name = _clean_name(data.get("name", ""))
        if await self.by_name(name):
            raise ConflictError(f"{name} is already in your supplier list")
        s = Supplier(name=name, **{k: (data.get(k) or None) for k in ("contact_name", "email", "phone", "notes")},
                     is_active=data.get("is_active", True) is not False)
        self.session.add(s)
        await self.session.flush()
        audit.record(self.session, actor, "supplier.create", "supplier", s.id, f"Supplier {name} added")
        await self.session.commit()
        await self.session.refresh(s)
        return s

    async def update(self, actor: User, supplier_id: int, data: dict[str, Any]) -> Supplier:
        s = await self.session.get(Supplier, supplier_id)
        if s is None:
            raise NotFoundError("Supplier not found")
        changes = []
        if "name" in data and data["name"] is not None:
            new = _clean_name(data["name"])
            if new != s.name:
                other = await self.by_name(new)
                if other and other.id != s.id:
                    raise ConflictError(f"{new} is already in your supplier list")
                old = s.name
                # Rename everywhere the name is used, so orders, listings and logins keep pointing at this supplier.
                for model, column in ((EtsyOrder, EtsyOrder.supplier), (EtsyListing, EtsyListing.internal_supplier),
                                      (User, User.supplier_name)):
                    await self.session.execute(update(model).where(func.lower(column) == old.lower()).values({column.key: new}))
                s.name = new
                changes.append(f"renamed from {old} to {new}")
        for k in ("contact_name", "email", "phone", "notes"):
            if k in data:
                v = (data[k] or "").strip() or None
                if v != getattr(s, k):
                    setattr(s, k, v)
                    changes.append(k.replace("_", " "))
        if "is_active" in data and data["is_active"] is not None and data["is_active"] != s.is_active:
            s.is_active = bool(data["is_active"])
            changes.append("switched on" if s.is_active else "switched off")
        if changes:
            audit.record(self.session, actor, "supplier.update", "supplier", s.id, f"Supplier {s.name}: {', '.join(changes)}")
            await self.session.commit()
            await self.session.refresh(s)
        return s
