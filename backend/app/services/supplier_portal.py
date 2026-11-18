"""What a supplier sees after signing in: only their own orders (order.supplier = their supplier name) on the external
shops they are allowed, with what they need to fulfil them — items, personalisation, ship-to address, ship-by date —
and what they are owed. Never the shop's revenue, profit, other suppliers or the buyer's email/phone."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.domain import channels as ch
from app.domain import etsy_payments, etsy_status
from app.models.etsy import EtsyOrder, EtsyOrderEvent, EtsyOrderItem
from app.models.user import User
from app.services.etsy_connection import EtsyConnectionService
from app.services.etsy_order_admin import EtsyOrderAdmin
from app.utils.text import escape_like

VIEWS = {
    "to_ship": ("new", "purchased"),
    "shipped": ("shipped", "delivered", "closed"),
}
SUPPLIER_EVENT_KINDS = ("created", "status", "tracking", "payment")  # never "costs" or team notes


class SupplierPortal:
    def __init__(self, session: AsyncSession, user: User):
        self.session = session
        self.user = user

    async def channels(self) -> list[str]:
        """Allowed for this supplier and connected right now."""
        allowed = [c for c in (self.user.supplier_channels or []) if c in ch.CHANNELS]
        out = []
        if "etsy" in allowed and (await EtsyConnectionService(self.session).status())["connected"]:
            out.append("etsy")
        return out

    async def me(self) -> dict[str, Any]:
        return {"supplier_name": self.user.supplier_name, "channels": await self.channels(),
                "names": {c: ch.CHANNELS[c] for c in ch.CHANNELS}}

    async def _guard(self, channel: str) -> str:
        if self.user.role != UserRole.SUPPLIER or not self.user.supplier_name:
            raise PermissionDeniedError("This login isn't linked to a supplier yet. Ask the shop owner.")
        if channel not in await self.channels():
            raise PermissionDeniedError("You don't have access to this shop")
        return self.user.supplier_name

    def _mine(self, name: str):
        return func.lower(EtsyOrder.supplier) == name.lower()

    async def orders(self, view: str, q: str | None, page: int, page_size: int) -> dict[str, Any]:
        name = await self._guard("etsy")
        cond = [self._mine(name)]
        if view in VIEWS:
            cond.append(EtsyOrder.status.in_(VIEWS[view]))
        if q:
            term = q.strip().lstrip("#")
            like = f"%{escape_like(term.lower())}%"
            parts = [func.lower(func.coalesce(EtsyOrder.buyer_name, "")).like(like),
                     func.lower(func.coalesce(EtsyOrder.supplier_order_number, "")).like(like),
                     exists().where(EtsyOrderItem.order_id == EtsyOrder.id, func.lower(EtsyOrderItem.title).like(like))]
            if term.isdigit():
                parts.append(EtsyOrder.etsy_receipt_id == int(term))
            cond.append(or_(*parts))
        total = (await self.session.execute(select(func.count()).select_from(EtsyOrder).where(*cond))).scalar_one()
        order_by = (EtsyOrder.ship_by.asc().nulls_last(), EtsyOrder.ordered_at) if view == "to_ship" else (EtsyOrder.ordered_at.desc(),)
        rows = (await self.session.execute(select(EtsyOrder).where(*cond).order_by(*order_by, EtsyOrder.id)
                                           .limit(page_size).offset((page - 1) * page_size))).scalars().all()
        admin = EtsyOrderAdmin(self.session)
        items = await admin._items([r.id for r in rows])
        images = await admin._images([i for its in items.values() for i in its])
        counts = dict((await self.session.execute(
            select(EtsyOrder.status, func.count()).where(self._mine(name)).group_by(EtsyOrder.status))).all())
        now = datetime.now(timezone.utc)
        return {
            "items": [self._row(o, items.get(o.id, []), images, now) for o in rows], "total": total, "page": page,
            "page_size": page_size,
            "counts": {"to_ship": sum(counts.get(s, 0) for s in VIEWS["to_ship"]),
                       "shipped": sum(counts.get(s, 0) for s in VIEWS["shipped"]), "all": sum(counts.values())},
        }

    def _row(self, o: EtsyOrder, items: list[EtsyOrderItem], images: dict[int, str], now: datetime) -> dict[str, Any]:
        waiting = o.status in VIEWS["to_ship"]
        return {
            "id": o.id, "etsy_receipt_id": o.etsy_receipt_id, "ordered_at": o.ordered_at, "ship_by": o.ship_by,
            "late": bool(waiting and o.ship_by and now > o.ship_by), "status": o.status,
            "status_label": etsy_status.LABELS.get(o.status, o.status), "buyer_name": o.buyer_name,
            "supplier_order_number": o.supplier_order_number, "carrier": o.carrier, "tracking_number": o.tracking_number,
            "items": [{"title": i.title, "quantity": i.quantity, "sku": i.sku, "variations": i.variations,
                       "image": images.get(i.etsy_listing_id or 0)} for i in items],
            "owed": etsy_payments.owed(o.purchase_cost, o.shipping_cost),
            "payment": etsy_payments.status(order_status=o.status, purchase_cost=o.purchase_cost, paid=o.supplier_paid_at is not None),
            "paid_at": o.supplier_paid_at, "paid_amount": o.supplier_paid_amount,
        }

    async def _own(self, order_id: int) -> EtsyOrder:
        name = await self._guard("etsy")
        o = await self.session.get(EtsyOrder, order_id)
        if o is None or (o.supplier or "").lower() != name.lower():
            raise NotFoundError("Order not found")  # someone else's order looks the same as a missing one
        return o

    async def detail(self, order_id: int) -> dict[str, Any]:
        o = await self._own(order_id)
        admin = EtsyOrderAdmin(self.session)
        items = (await admin._items([o.id])).get(o.id, [])
        events = (await self.session.execute(
            select(EtsyOrderEvent).where(EtsyOrderEvent.order_id == o.id, EtsyOrderEvent.kind.in_(SUPPLIER_EVENT_KINDS))
            .order_by(EtsyOrderEvent.id.desc()))).scalars().all()
        return {
            **self._row(o, items, await admin._images(items), datetime.now(timezone.utc)),
            "ship_address": o.ship_address, "gift_message": o.gift_message, "buyer_note": o.buyer_note,
            "shipped_at": o.shipped_at, "payment_ref": o.supplier_payment_ref,
            "history": [{"id": e.id, "message": e.message, "source": e.source, "actor_name": e.actor_name,
                         "created_at": e.created_at} for e in events],
        }

    async def update(self, order_id: int, patch: dict[str, Any]) -> dict[str, Any]:
        o = await self._own(order_id)
        allowed = {k: v for k, v in patch.items() if k in ("supplier_order_number", "carrier", "tracking_number")}
        await EtsyOrderAdmin(self.session).update(o.id, self.user, allowed)
        return await self.detail(o.id)

    async def mark_shipped(self, order_id: int, carrier: str | None, tracking_number: str) -> dict[str, Any]:
        o = await self._own(order_id)
        if o.status not in VIEWS["to_ship"]:
            raise ValidationFailedError("Only an order that is still to ship can be marked shipped")
        if not tracking_number.strip():
            raise ValidationFailedError("Enter the tracking number")
        admin = EtsyOrderAdmin(self.session)
        await admin.update(o.id, self.user, {"tracking_number": tracking_number, **({"carrier": carrier} if carrier else {})})
        await admin.set_status(o.id, self.user, etsy_status.SHIPPED, "Marked shipped by the supplier")
        return await self.detail(o.id)

    async def payments_filter(self) -> str:
        return await self._guard("etsy")
