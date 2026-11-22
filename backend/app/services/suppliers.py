"""The supplier list: who the shop buys from. Listings, orders and supplier logins pick a supplier from it (they keep its
name); renaming a supplier renames it everywhere. Suppliers are switched off, never deleted, so history stays."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
                "notes": s.notes, "is_active": s.is_active, "crm_id": s.crm_id, "listings": listings.get(k, 0), "open_orders": open_orders.get(k, 0),
                "owed": Decimal(owed.get(k) or 0).quantize(Decimal("0.01")), "logins": logins.get(k, 0),
            })
        return out

    async def managed_by_crm(self) -> bool:
        """Once the CRM has sent any supplier, the CRM owns the list and the shop's copy is read-only."""
        return (await self.session.execute(select(func.count()).select_from(Supplier).where(Supplier.crm_id.is_not(None)))).scalar_one() > 0

    async def _refuse_if_crm(self) -> None:
        if await self.managed_by_crm():
            raise ConflictError("Suppliers are managed in the CRM now. Add or change them there; they reach the shop within minutes.")

    async def create(self, actor: User, data: dict[str, Any]) -> Supplier:
        await self._refuse_if_crm()
        return await self._create(actor, data)

    async def _create(self, actor: User | None, data: dict[str, Any]) -> Supplier:
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
        await self._refuse_if_crm()
        return await self._update(actor, supplier_id, data)

    async def _update(self, actor: User | None, supplier_id: int, data: dict[str, Any]) -> Supplier:
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


    # ---- the CRM (app/api/v1/crm_suppliers.py) -------------------------------------------------------------------

    async def from_crm(self, data: dict[str, Any]) -> tuple[Supplier, str]:
        """Apply one supplier sent by the CRM: the linked one, else the one with the same name (now linked), else a new
        one. Renames reach orders, listings and logins as usual. Returns the supplier and what happened."""
        crm_id = int(data["crm_id"])
        fields = {k: data.get(k) for k in ("name", "contact_name", "email", "phone") if k in data}
        fields["is_active"] = bool(data.get("is_active", True))
        s = (await self.session.execute(select(Supplier).where(Supplier.crm_id == crm_id))).scalar_one_or_none()
        outcome = "updated"
        if s is None:
            s = await self.by_name(_clean_name(data.get("name", "")))
            if s is not None and s.crm_id is not None:
                raise ConflictError(f"{s.name} is already linked to another CRM supplier")
            outcome = "linked" if s is not None else "created"
        if s is None:
            s = await self._create(None, fields)
        else:
            s = await self._update(None, s.id, fields)
        s.crm_id, s.crm_synced_at = crm_id, datetime.now(timezone.utc)
        await self.session.commit()
        return s, outcome

    async def stats(self, name: str) -> dict[str, Any]:
        """A supplier's figures for the CRM's supplier page: orders, money owed and paid, shipping speed."""
        key = name.strip().lower()
        mine = func.lower(EtsyOrder.supplier) == key
        orders = (await self.session.execute(select(EtsyOrder).where(mine))).scalars().all()
        listings = (await self.session.execute(
            select(func.count()).select_from(EtsyListing).where(func.lower(EtsyListing.internal_supplier) == key))).scalar_one()
        since = datetime.now(timezone.utc) - timedelta(days=90)
        live = [o for o in orders if o.status != "cancelled"]
        shipped = [o for o in live if o.shipped_at and o.paid_at and o.paid_at >= since]
        timed = [o for o in shipped if o.ship_by]
        owed = sum(((o.purchase_cost or Decimal(0)) + (o.shipping_cost or Decimal(0))
                    for o in live if o.purchase_cost is not None and o.supplier_paid_at is None), Decimal(0))
        paid = sum((o.supplier_paid_amount or Decimal(0) for o in orders if o.supplier_paid_at), Decimal(0))
        cents = Decimal("0.01")
        return {
            "name": name, "listings": listings, "orders": len(live),
            "open_orders": sum(o.status in etsy_status.OPEN_STATUSES for o in live),
            "to_ship": sum(o.status in ("new", "purchased") for o in live),
            "late": sum(o.status in ("new", "purchased") and o.ship_by is not None and o.ship_by < datetime.now(timezone.utc) for o in live),
            "owed": owed.quantize(cents), "owed_orders": sum(o.purchase_cost is not None and o.supplier_paid_at is None for o in live),
            "paid": paid.quantize(cents),
            "avg_days_to_ship_90d": round(sum((o.shipped_at - o.paid_at).days for o in shipped) / len(shipped), 1) if shipped else None,
            "on_time_rate_90d": round(sum(o.shipped_at <= o.ship_by for o in timed) / len(timed), 4) if timed else None,
            "last_order_at": max((o.ordered_at for o in orders), default=None),
        }
