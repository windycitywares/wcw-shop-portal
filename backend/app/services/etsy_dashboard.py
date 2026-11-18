"""Loads the Etsy orders for a period and hands them to app/domain/etsy_dashboard.py."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import etsy_dashboard as dash
from app.domain.timeutil import DateRange, to_store_time
from app.models.etsy import EtsyListing, EtsyOrder, EtsyOrderItem
from app.services.reports.common import bucket_label, bucket_starts, kpi


class EtsyDashboard:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _orders(self, rng: DateRange, listing_id: int | None, supplier: str | None) -> list[dash.Order]:
        cond = [EtsyOrder.ordered_at >= rng.start_utc, EtsyOrder.ordered_at < rng.end_utc]
        if listing_id:
            cond.append(exists().where(EtsyOrderItem.order_id == EtsyOrder.id, EtsyOrderItem.etsy_listing_id == listing_id))
        if supplier == "__none__":
            cond.append(EtsyOrder.supplier.is_(None))
        elif supplier:
            cond.append(func.lower(EtsyOrder.supplier) == supplier.lower())
        rows = (await self.session.execute(select(EtsyOrder).where(*cond))).scalars().all()
        items: dict[int, list[dash.Item]] = {}
        if rows:
            for it in (await self.session.execute(
                    select(EtsyOrderItem).where(EtsyOrderItem.order_id.in_([r.id for r in rows])))).scalars():
                items.setdefault(it.order_id, []).append(
                    dash.Item(it.etsy_listing_id, it.title, it.quantity, it.unit_price * it.quantity))
        return [dash.Order(
            status=o.status, ordered_at=o.ordered_at, paid_at=o.paid_at, shipped_at=o.shipped_at, ship_by=o.ship_by,
            items_total=o.items_total, shipping_charged=o.shipping_charged, discounts=o.discounts,
            purchase_cost=o.purchase_cost, shipping_cost=o.shipping_cost, etsy_fees=o.etsy_fees, supplier=o.supplier,
            state=(o.ship_address or {}).get("state"), country=(o.ship_address or {}).get("country_iso"),
            items=tuple(items.get(o.id, ())),
        ) for o in rows]

    async def build(self, rng: DateRange, listing_id: int | None = None, supplier: str | None = None) -> dict[str, Any]:
        gran = rng.granularity()
        buckets = bucket_starts(rng)

        def bucket_of(moment: datetime) -> date:
            day = to_store_time(moment).date()
            if gran == "week":
                return day - timedelta(days=day.weekday())
            if gran == "month":
                return day.replace(day=1)
            return day

        prev = rng.previous()
        out = dash.build(await self._orders(rng, listing_id, supplier), await self._orders(prev, listing_id, supplier),
                         buckets, bucket_of)
        for s in out["series"]:
            s["label"] = bucket_label(date.fromisoformat(s["bucket"]), gran)
        t, p = out["totals"], out["previous"]
        out["kpis"] = [
            kpi("orders", "Orders", t["orders"], p["orders"], help="Paid, not cancelled."),
            kpi("items", "Items sold", t["units"], p["units"], help="What Etsy calls “sales”."),
            kpi("revenue", "Revenue", t["revenue"], p["revenue"], "money", "After discounts, before tax."),
            kpi("profit", "Net profit", t["profit"], p["profit"], "money", "Costed orders, before Etsy fees."),
            kpi("margin", "Margin", t["margin"], p["margin"], "percent", "Of costed orders."),
            kpi("days_to_ship", "Days to ship", t["avg_days_to_ship"], p["avg_days_to_ship"], "decimal",
                "Payment to shipping.", better="down"),
        ]
        out["range"] = {"start": rng.start.isoformat(), "end": rng.end.isoformat(), "days": rng.days, "granularity": gran,
                        "previous_start": prev.start.isoformat(), "previous_end": prev.end.isoformat()}
        out["options"] = await self._options()
        ids = [p["listing_id"] for p in out["top_products"] if p["listing_id"]]
        if ids:
            imgs = dict((await self.session.execute(
                select(EtsyListing.etsy_listing_id, EtsyListing.images).where(EtsyListing.etsy_listing_id.in_(ids)))).all())
            for p in out["top_products"]:
                p["image"] = (imgs.get(p["listing_id"]) or [None])[0]
        return out

    async def _options(self) -> dict[str, Any]:
        """What the filters offer: products that have sold, and suppliers on orders."""
        products = (await self.session.execute(
            select(EtsyOrderItem.etsy_listing_id, func.max(EtsyOrderItem.title), func.count())
            .where(EtsyOrderItem.etsy_listing_id.is_not(None))
            .group_by(EtsyOrderItem.etsy_listing_id).order_by(func.max(EtsyOrderItem.title)))).all()
        suppliers = (await self.session.execute(
            select(EtsyOrder.supplier).where(EtsyOrder.supplier.is_not(None)).distinct().order_by(EtsyOrder.supplier))).scalars().all()
        return {"products": [{"listing_id": lid, "title": title} for lid, title, _ in products], "suppliers": list(suppliers)}
