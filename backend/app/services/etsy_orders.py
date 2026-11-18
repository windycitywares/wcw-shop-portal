"""Etsy orders → the shop, one way. A paid Etsy order is created here automatically; later syncs refresh what Etsy says
(prices, address, shipped, cancelled) and never touch what the team entered. Status only moves the way
app/domain/etsy_status.py allows, and every change is written to the order's history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import etsy_receipt, etsy_status
from app.models.etsy import EtsyListing, EtsyOrder, EtsyOrderEvent, EtsyOrderItem
from app.services import etsy_client
from app.services.etsy_client import EtsyError
from app.services.etsy_connection import EtsyConnectionService

PAGE = 100
EVERY = timedelta(minutes=5)
FIRST_LOOKBACK = timedelta(days=180)  # the first run brings in the recent past
LOOKBACK = timedelta(days=45)  # later runs re-read this window, so shipped / cancelled changes on older orders arrive too

# Fields copied from Etsy on every sync. The team's own columns are never in this list.
ETSY_FIELDS = (
    "etsy_state", "ship_by", "buyer_name", "etsy_buyer_id", "buyer_email", "ship_address", "gift_message", "buyer_note",
    "currency", "items_total", "shipping_charged", "discounts", "tax", "grand_total", "etsy_updated_at",
)


def _event(order_id: int, kind: str, message: str, frm: str | None = None, to: str | None = None) -> EtsyOrderEvent:
    return EtsyOrderEvent(order_id=order_id, kind=kind, from_status=frm, to_status=to, message=message[:500], source="etsy",
                          actor_name="Etsy")


class EtsyOrderSync:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self, force: bool = False) -> dict[str, Any]:
        service = EtsyConnectionService(self.session)
        conn = await service.row()
        if not (conn.access_token and conn.etsy_shop_id):
            return {"skipped": "not connected"}
        now = datetime.now(timezone.utc)
        if not force and conn.orders_synced_at and now - conn.orders_synced_at < EVERY:
            return {"skipped": "not due"}
        since = now - (LOOKBACK if conn.orders_synced_at else FIRST_LOOKBACK)
        created = updated = 0
        try:
            key, token = await service.access_token()
            offset = 0
            while True:
                data = await etsy_client.get(
                    f"/shops/{conn.etsy_shop_id}/receipts", api_key=key, access_token=token,
                    params={"min_created": int(since.timestamp()), "limit": PAGE, "offset": offset,
                            "sort_on": "created", "sort_order": "asc"})
                results = data.get("results") or []
                for raw in results:
                    c = await self._apply(etsy_receipt.parse(raw), now)
                    created, updated = created + (c == "created"), updated + (c == "updated")
                offset += PAGE
                if len(results) < PAGE:
                    break
        except EtsyError as exc:
            await self.session.rollback()
            await service.fail(f"Order sync: {exc}")
            return {"error": str(exc)[:200]}
        conn = await service.row()
        conn.orders_synced_at, conn.last_error, conn.last_error_at = now, None, None
        await self.session.commit()
        return {"created": created, "updated": updated}

    async def _apply(self, parsed: dict[str, Any], now: datetime) -> str | None:
        o, items = dict(parsed["order"]), parsed["items"]
        implied, etsy_track, etsy_carrier = o.pop("implied_status"), o.pop("etsy_tracking"), o.pop("etsy_carrier")
        etsy_shipped = o.pop("etsy_shipped_at")
        row = (await self.session.execute(
            select(EtsyOrder).where(EtsyOrder.etsy_receipt_id == o["etsy_receipt_id"]))).scalar_one_or_none()
        if row is None:
            if not o["paid_at"] or not o["ordered_at"]:
                return None  # not paid (yet): an order starts when Etsy says it is paid
            return await self._create(o, items, implied, etsy_track, etsy_carrier, etsy_shipped or now)
        for k in ETSY_FIELDS:
            setattr(row, k, o[k])
        row.synced_at = now
        if o["paid_at"] and not row.paid_at:
            row.paid_at = o["paid_at"]
        target = etsy_status.sync_target(row.status, implied)
        if target != row.status:
            self.session.add(_event(row.id, "status", f"Etsy: {etsy_status.LABELS[row.status]} → {etsy_status.LABELS[target]}", row.status, target))
            row.status = target
            if target in (etsy_status.SHIPPED, etsy_status.DELIVERED):
                row.shipped_at = row.shipped_at or etsy_shipped or now
            if target == etsy_status.DELIVERED:
                row.delivered_at = row.delivered_at or now
        if etsy_track and not row.tracking_number:
            row.tracking_number, row.carrier, row.tracking_sent_at = etsy_track, etsy_carrier, now  # Etsy already has it
            self.session.add(_event(row.id, "tracking", f"Etsy has tracking {etsy_track}"))
        await self._add_missing_items(row.id, items)
        return "updated"

    async def _create(self, o, items, implied, etsy_track, etsy_carrier, shipped_at) -> str:
        now = datetime.now(timezone.utc)
        cost, supplier = await self._defaults(items)
        row = EtsyOrder(
            **{k: v for k, v in o.items() if k not in ("paid_at",)}, paid_at=o["paid_at"], status=implied, synced_at=now,
            purchase_cost=cost, costs_prefilled=cost is not None, supplier=supplier,
            tracking_number=etsy_track, carrier=etsy_carrier, tracking_sent_at=now if etsy_track else None,
            shipped_at=shipped_at if implied in (etsy_status.SHIPPED, etsy_status.DELIVERED) else None,
            delivered_at=now if implied == etsy_status.DELIVERED else None,
        )
        self.session.add(row)
        await self.session.flush()
        self.session.add(_event(row.id, "created", f"Order {row.etsy_receipt_id} arrived from Etsy", None, implied))
        for it in items:
            self.session.add(EtsyOrderItem(order_id=row.id, **it))
        return "created"

    async def _add_missing_items(self, order_id: int, items: list[dict[str, Any]]) -> None:
        have = set((await self.session.execute(
            select(EtsyOrderItem.etsy_transaction_id).where(EtsyOrderItem.order_id == order_id))).scalars().all())
        for it in items:
            if it["etsy_transaction_id"] not in have:
                self.session.add(EtsyOrderItem(order_id=order_id, **it))

    async def _defaults(self, items: list[dict[str, Any]]) -> tuple[Decimal | None, str | None]:
        """Start the cost from the listings' default cost (only when every item has one) and the supplier (when it is one)."""
        ids = {i["etsy_listing_id"] for i in items if i["etsy_listing_id"]}
        if not ids or any(i["etsy_listing_id"] is None for i in items):
            return None, None
        listings = {l.etsy_listing_id: l for l in (await self.session.execute(
            select(EtsyListing).where(EtsyListing.etsy_listing_id.in_(ids)))).scalars()}
        total = Decimal("0.00")
        for i in items:
            l = listings.get(i["etsy_listing_id"])
            if l is None or l.internal_purchase_cost is None:
                return None, None
            total += l.internal_purchase_cost * i["quantity"]
        suppliers = {l.internal_supplier for l in listings.values() if l.internal_supplier}
        return total, (suppliers.pop() if len(suppliers) == 1 else None)
