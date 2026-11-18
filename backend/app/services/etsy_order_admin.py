"""What the team does with Etsy orders: find them, enter costs and tracking, change status. Every change is written to the
order's history (who, when, what) and to the audit log. Etsy's own fields are never edited here."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.domain import etsy_attention, etsy_payments, etsy_profit, etsy_status
from app.models.etsy import EtsyListing, EtsyOrder, EtsyOrderEvent, EtsyOrderItem
from app.models.user import User
from app.services import audit
from app.utils.text import escape_like

COST_FIELDS = ("purchase_cost", "shipping_cost", "supplier", "supplier_order_number")
TRACKING_FIELDS = ("carrier", "tracking_number")
OTHER_FIELDS = ("notes", "buyer_phone")
EDITABLE = COST_FIELDS + TRACKING_FIELDS + OTHER_FIELDS
LABEL = {
    "purchase_cost": "purchase cost", "shipping_cost": "shipping cost", "supplier": "supplier",
    "supplier_order_number": "supplier order number", "carrier": "carrier", "tracking_number": "tracking number",
    "notes": "notes", "buyer_phone": "buyer phone",
}


def facts(o: EtsyOrder) -> etsy_attention.OrderFacts:
    return etsy_attention.OrderFacts(
        status=o.status, paid_at=o.paid_at, ship_by=o.ship_by, purchase_cost=o.purchase_cost, shipping_cost=o.shipping_cost,
        etsy_fees=o.etsy_fees, items_total=o.items_total, shipping_charged=o.shipping_charged, discounts=o.discounts,
        past_order=o.past_order)


def profit(o: EtsyOrder) -> dict[str, Any]:
    p = etsy_profit.compute(items_total=o.items_total, shipping_charged=o.shipping_charged, discounts=o.discounts,
                            purchase_cost=o.purchase_cost, shipping_cost=o.shipping_cost, etsy_fees=o.etsy_fees)
    return {"revenue": p.revenue, "total_cost": p.total_cost, "net_profit": p.net_profit, "margin_pct": p.margin_pct,
            "missing": list(p.missing), "days_to_ship": etsy_profit.days_to_ship(o.paid_at, o.shipped_at)}


def _attention_sql(now: datetime):
    revenue = EtsyOrder.items_total + EtsyOrder.shipping_charged - EtsyOrder.discounts
    cost = (func.coalesce(EtsyOrder.purchase_cost, 0) + func.coalesce(EtsyOrder.shipping_cost, 0)
            + func.coalesce(EtsyOrder.etsy_fees, 0))
    return and_(EtsyOrder.status != "cancelled", EtsyOrder.past_order.is_(False), or_(
        and_(EtsyOrder.status == "new", EtsyOrder.paid_at < now - etsy_attention.NOT_PURCHASED_AFTER),
        and_(EtsyOrder.status.in_(etsy_attention.WAITING), EtsyOrder.ship_by < now),
        EtsyOrder.purchase_cost.is_(None),
        and_(EtsyOrder.shipping_cost.is_(None), EtsyOrder.status.in_(etsy_attention.DONE_SHIPPING)),
        and_(EtsyOrder.purchase_cost.is_not(None), revenue - cost < 0),
    ))


class EtsyOrderAdmin:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self, *, q: str | None, status: str | None, attention: bool, supplier: str | None, listing_id: int | None,
        date_from: date | None, date_to: date | None, page: int, page_size: int,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        cond = []
        if q:
            term = q.strip().lstrip("#")
            like = f"%{escape_like(term.lower())}%"
            parts = [func.lower(func.coalesce(EtsyOrder.buyer_name, "")).like(like, escape="\\"),
                     func.lower(func.coalesce(EtsyOrder.tracking_number, "")).like(like, escape="\\"),
                     func.lower(func.coalesce(EtsyOrder.supplier_order_number, "")).like(like, escape="\\"),
                     exists().where(EtsyOrderItem.order_id == EtsyOrder.id,
                                    or_(func.lower(EtsyOrderItem.title).like(like, escape="\\"),
                                        func.lower(func.coalesce(EtsyOrderItem.sku, "")).like(like, escape="\\")))]
            if term.isdigit():
                parts.append(EtsyOrder.etsy_receipt_id == int(term))
            cond.append(or_(*parts))
        if status == "open":
            cond.append(EtsyOrder.status.in_(etsy_status.OPEN_STATUSES))
        elif status:
            cond.append(EtsyOrder.status == status)
        if attention:
            cond.append(_attention_sql(now))
        if supplier == "__none__":
            cond.append(EtsyOrder.supplier.is_(None))
        elif supplier:  # picked from the supplier list, so an exact (case-blind) match
            cond.append(func.lower(EtsyOrder.supplier) == supplier.strip().lower())
        if listing_id:
            cond.append(exists().where(EtsyOrderItem.order_id == EtsyOrder.id, EtsyOrderItem.etsy_listing_id == listing_id))
        if date_from:
            cond.append(EtsyOrder.ordered_at >= datetime.combine(date_from, time.min, timezone.utc))
        if date_to:
            cond.append(EtsyOrder.ordered_at < datetime.combine(date_to + timedelta(days=1), time.min, timezone.utc))
        total = (await self.session.execute(select(func.count()).select_from(EtsyOrder).where(*cond))).scalar_one()
        rows = (await self.session.execute(
            select(EtsyOrder).where(*cond).order_by(EtsyOrder.ordered_at.desc(), EtsyOrder.id.desc())
            .limit(page_size).offset((page - 1) * page_size))).scalars().all()
        items = await self._items([r.id for r in rows])
        images = await self._images([i for its in items.values() for i in its])
        counts = dict((await self.session.execute(select(EtsyOrder.status, func.count()).group_by(EtsyOrder.status))).all())
        needing = (await self.session.execute(select(func.count()).select_from(EtsyOrder).where(_attention_sql(now)))).scalar_one()
        return {
            "items": [self.summary(r, items.get(r.id, []), now, images) for r in rows], "total": total, "page": page,
            "page_size": page_size, "counts": counts, "attention": needing,
        }

    async def _items(self, ids: list[int]) -> dict[int, list[EtsyOrderItem]]:
        out: dict[int, list[EtsyOrderItem]] = {}
        if ids:
            for it in (await self.session.execute(select(EtsyOrderItem).where(EtsyOrderItem.order_id.in_(ids)).order_by(EtsyOrderItem.id))).scalars():
                out.setdefault(it.order_id, []).append(it)
        return out

    async def _images(self, items: list[EtsyOrderItem]) -> dict[int, str]:
        """First photo of each listing in these items (for thumbnails)."""
        ids = {i.etsy_listing_id for i in items if i.etsy_listing_id}
        if not ids:
            return {}
        rows = (await self.session.execute(
            select(EtsyListing.etsy_listing_id, EtsyListing.images).where(EtsyListing.etsy_listing_id.in_(ids)))).all()
        return {lid: imgs[0] for lid, imgs in rows if imgs}

    @staticmethod
    def summary(o: EtsyOrder, items: list[EtsyOrderItem], now: datetime, images: dict[int, str] | None = None) -> dict[str, Any]:
        images = images or {}
        return {
            "id": o.id, "etsy_receipt_id": o.etsy_receipt_id, "status": o.status, "ordered_at": o.ordered_at,
            "paid_at": o.paid_at, "ship_by": o.ship_by, "buyer_name": o.buyer_name, "supplier": o.supplier,
            "currency": o.currency, "tracking_number": o.tracking_number, "past_order": o.past_order,
            "items": [{"title": i.title, "quantity": i.quantity, "image": images.get(i.etsy_listing_id or 0)} for i in items],
            "profit": profit(o), "attention": etsy_attention.reasons(facts(o), now),
        }

    async def get(self, order_id: int) -> EtsyOrder:
        row = await self.session.get(EtsyOrder, order_id)
        if row is None:
            raise NotFoundError("Order not found")
        return row

    async def detail(self, order_id: int) -> dict[str, Any]:
        o = await self.get(order_id)
        now = datetime.now(timezone.utc)
        items = (await self._items([o.id])).get(o.id, [])
        images = await self._images(items)
        events = (await self.session.execute(
            select(EtsyOrderEvent).where(EtsyOrderEvent.order_id == o.id).order_by(EtsyOrderEvent.id.desc()))).scalars().all()
        return {
            **self.summary(o, items, now, images),
            "etsy_state": o.etsy_state, "etsy_buyer_id": o.etsy_buyer_id, "buyer_email": o.buyer_email,
            "buyer_phone": o.buyer_phone, "ship_address": o.ship_address, "gift_message": o.gift_message,
            "buyer_note": o.buyer_note, "items_total": o.items_total, "shipping_charged": o.shipping_charged,
            "discounts": o.discounts, "tax": o.tax, "grand_total": o.grand_total, "etsy_fees": o.etsy_fees,
            "purchase_cost": o.purchase_cost, "costs_prefilled": o.costs_prefilled,
            "supplier_order_number": o.supplier_order_number, "shipping_cost": o.shipping_cost, "carrier": o.carrier,
            "tracking_sent_at": o.tracking_sent_at, "tracking_error": o.tracking_error, "purchased_at": o.purchased_at,
            "shipped_at": o.shipped_at, "delivered_at": o.delivered_at, "notes": o.notes, "synced_at": o.synced_at,
            "etsy_url": f"https://www.etsy.com/your/orders/sold?order_id={o.etsy_receipt_id}",
            "supplier_owed": etsy_payments.owed(o.purchase_cost, o.shipping_cost),
            "supplier_payment": etsy_payments.status(order_status=o.status, purchase_cost=o.purchase_cost, paid=o.supplier_paid_at is not None),
            "supplier_paid_at": o.supplier_paid_at, "supplier_paid_amount": o.supplier_paid_amount,
            "supplier_payment_ref": o.supplier_payment_ref, "supplier_paid_by": o.supplier_paid_by,
            "line_items": [{"id": i.id, "etsy_listing_id": i.etsy_listing_id, "title": i.title, "sku": i.sku,
                            "image": images.get(i.etsy_listing_id or 0),
                            "variations": i.variations, "quantity": i.quantity, "unit_price": i.unit_price} for i in items],
            "history": [{"id": e.id, "kind": e.kind, "from_status": e.from_status, "to_status": e.to_status,
                         "message": e.message, "source": e.source, "actor_name": e.actor_name, "created_at": e.created_at}
                        for e in events],
        }

    def _event(self, o: EtsyOrder, actor: User, kind: str, message: str, frm: str | None = None, to: str | None = None) -> None:
        self.session.add(EtsyOrderEvent(order_id=o.id, kind=kind, from_status=frm, to_status=to, message=message[:500],
                                        source="team", actor_id=actor.id, actor_name=actor.full_name or actor.email))

    async def update(self, order_id: int, actor: User, patch: dict[str, Any]) -> dict[str, Any]:
        o = await self.get(order_id)
        unknown = set(patch) - set(EDITABLE)
        if unknown:
            raise ValidationFailedError(f"Not editable here: {', '.join(sorted(unknown))}")
        if patch.get("supplier") is not None:
            if patch["supplier"].strip().lower() == (o.supplier or "").lower():
                patch = {**patch, "supplier": o.supplier}  # unchanged (even if that supplier was switched off since)
            else:
                from app.services.suppliers import SupplierDirectory

                patch = {**patch, "supplier": await SupplierDirectory(self.session).resolve(patch["supplier"])}
        changed: dict[str, list[str]] = {"costs": [], "tracking": [], "note": []}
        for k, v in patch.items():
            if isinstance(v, str):
                v = v.strip() or None
            if getattr(o, k) == v:
                continue
            old = getattr(o, k)
            setattr(o, k, v)
            kind = "costs" if k in COST_FIELDS else "tracking" if k in TRACKING_FIELDS else "note"
            changed[kind].append(f"{LABEL[k]}: {_show(old)} → {_show(v)}" if k != "notes" else "notes changed")
        if not any(changed.values()):
            return await self.detail(o.id)
        if changed["costs"]:
            o.costs_prefilled = False if "purchase_cost" in patch else o.costs_prefilled
        if changed["tracking"]:
            o.tracking_sent_at, o.tracking_error = None, None  # phase 2 sends the new number to Etsy
        for kind, lines in changed.items():
            if lines:
                self._event(o, actor, kind, "; ".join(lines))
        audit.record(self.session, actor, "etsy.order.update", "etsy_order", o.id,
                     f"Etsy order {o.etsy_receipt_id}: " + "; ".join(sum(changed.values(), [])),
                     {"fields": sorted(k for k in patch if k in EDITABLE)})
        await self.session.commit()
        return await self.detail(o.id)

    async def set_status(self, order_id: int, actor: User, status: str, note: str | None) -> dict[str, Any]:
        o = await self.get(order_id)
        if not etsy_status.is_valid(status):
            raise ValidationFailedError("Unknown status")
        if not etsy_status.can_set_by_team(o.status, status):
            raise ValidationFailedError("The order already has that status")
        now = datetime.now(timezone.utc)
        old = o.status
        o.status = status
        if status == etsy_status.PURCHASED and not o.purchased_at:
            o.purchased_at = now
        if status in (etsy_status.SHIPPED, etsy_status.DELIVERED) and not o.shipped_at:
            o.shipped_at = now
        if status == etsy_status.DELIVERED and not o.delivered_at:
            o.delivered_at = now
        msg = f"{etsy_status.LABELS[old]} → {etsy_status.LABELS[status]}" + (f": {note.strip()}" if note and note.strip() else "")
        self._event(o, actor, "status", msg, old, status)
        audit.record(self.session, actor, "etsy.order.status", "etsy_order", o.id, f"Etsy order {o.etsy_receipt_id}: {msg}")
        await self.session.commit()
        return await self.detail(o.id)


def _show(v: Any) -> str:
    if v is None:
        return "empty"
    if isinstance(v, Decimal):
        return f"${v:.2f}"
    return str(v)[:60]
