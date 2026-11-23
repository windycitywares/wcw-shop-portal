"""Etsy work handed to the CRM (docs/CRM_SYNC.md → "Etsy move"). Etsy itself now syncs into the CRM; this hands over
what only the shop knows — the team's costs, suppliers, notes, tracking, history and supplier payments — so the CRM
can copy them once. Read-only, same bearer token as the rest of /integrations/crm; supplier given by name and by the
CRM supplier id it mirrors. Buyer details are not included (the CRM has them from Etsy)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import SessionDep
from app.api.v1.crm_read import Token
from app.models.etsy import EtsyListing, EtsyOrder, EtsyOrderEvent
from app.models.supplier import Supplier

router = APIRouter(prefix="/integrations/crm/etsy", tags=["integrations"], include_in_schema=False)

ORDER_FIELDS = ("purchase_cost", "costs_prefilled", "past_order", "supplier_order_number", "supplier_paid_at",
                "supplier_paid_amount", "supplier_payment_ref", "supplier_paid_by", "shipping_cost", "carrier",
                "tracking_number", "tracking_sent_at", "purchased_at", "shipped_at", "delivered_at", "notes",
                "buyer_phone", "status")


async def _crm_ids(session) -> dict[str, int | None]:
    rows = (await session.execute(select(Supplier.name, Supplier.crm_id))).all()
    return {name.lower(): crm_id for name, crm_id in rows}


@router.get("/counts", dependencies=[Token])
async def counts(session: SessionDep) -> dict[str, int]:
    """What the CRM should end up with, to check the copy."""
    one = lambda stmt: session.execute(stmt)  # noqa: E731
    return {
        "listings_with_team_data": (await one(select(func.count()).select_from(EtsyListing).where(
            (EtsyListing.internal_supplier.is_not(None)) | (EtsyListing.internal_purchase_cost.is_not(None))
            | (EtsyListing.internal_notes.is_not(None))))).scalar_one(),
        "orders": (await one(select(func.count()).select_from(EtsyOrder))).scalar_one(),
        "orders_with_cost": (await one(select(func.count()).select_from(EtsyOrder)
                                       .where(EtsyOrder.purchase_cost.is_not(None)))).scalar_one(),
        "orders_with_supplier": (await one(select(func.count()).select_from(EtsyOrder)
                                           .where(EtsyOrder.supplier.is_not(None)))).scalar_one(),
        "orders_paid": (await one(select(func.count()).select_from(EtsyOrder)
                                  .where(EtsyOrder.supplier_paid_at.is_not(None)))).scalar_one(),
        "team_events": (await one(select(func.count()).select_from(EtsyOrderEvent)
                                  .where(EtsyOrderEvent.source == "team"))).scalar_one(),
    }


@router.get("/listings", dependencies=[Token])
async def listings(session: SessionDep, after_id: int = Query(0, ge=0),
                   limit: int = Query(200, ge=1, le=500)) -> dict[str, Any]:
    """Listings the team has put a supplier, cost or note on."""
    ids = await _crm_ids(session)
    rows = (await session.execute(select(EtsyListing).where(
        EtsyListing.id > after_id,
        (EtsyListing.internal_supplier.is_not(None)) | (EtsyListing.internal_purchase_cost.is_not(None))
        | (EtsyListing.internal_notes.is_not(None))).order_by(EtsyListing.id).limit(limit))).scalars().all()
    return {"items": [{
        "id": r.id, "etsy_listing_id": r.etsy_listing_id, "supplier": r.internal_supplier,
        "supplier_crm_id": ids.get((r.internal_supplier or "").lower()), "purchase_cost": r.internal_purchase_cost,
        "notes": r.internal_notes} for r in rows], "next_after_id": rows[-1].id if len(rows) == limit else None}


@router.get("/orders", dependencies=[Token])
async def orders(session: SessionDep, after_id: int = Query(0, ge=0),
                 limit: int = Query(100, ge=1, le=200)) -> dict[str, Any]:
    """Every order's team fields, with the team's history lines (Etsy's own lines the CRM writes itself)."""
    ids = await _crm_ids(session)
    rows = (await session.execute(select(EtsyOrder).where(EtsyOrder.id > after_id).order_by(EtsyOrder.id)
                                  .limit(limit))).scalars().all()
    events: dict[int, list[dict[str, Any]]] = {}
    if rows:
        for e in (await session.execute(select(EtsyOrderEvent).where(
                EtsyOrderEvent.order_id.in_([r.id for r in rows]), EtsyOrderEvent.source == "team")
                .order_by(EtsyOrderEvent.id))).scalars():
            events.setdefault(e.order_id, []).append({
                "kind": e.kind, "from_status": e.from_status, "to_status": e.to_status, "message": e.message,
                "actor_name": e.actor_name, "created_at": e.created_at})
    return {"items": [{
        "id": r.id, "etsy_receipt_id": r.etsy_receipt_id, "supplier": r.supplier,
        "supplier_crm_id": ids.get((r.supplier or "").lower()), **{f: getattr(r, f) for f in ORDER_FIELDS},
        "events": events.get(r.id, [])} for r in rows], "next_after_id": rows[-1].id if len(rows) == limit else None}
