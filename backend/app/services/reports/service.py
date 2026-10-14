"""One entry point for the report endpoints: loads the store settings the reports depend on, then builds the report."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.timeutil import DateRange
from app.services.reports import customers, exports, insights, inventory, overview, products, promotions, sales, traffic
from app.services.reports import common as c
from app.services.settings import SettingsService

SEVERITIES = ("critical", "warning", "opportunity", "info", "success")


class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _context(self) -> tuple[dict[str, bool], int, Decimal | None]:
        """(setup checklist, low-stock level, free-shipping threshold)"""
        settings = SettingsService(self.session)
        loaded = await settings.load()
        return await settings.setup_checklist(), loaded.general.low_stock_threshold, loaded.shipping.free_threshold

    async def overview(self, rng: DateRange) -> dict[str, Any]:
        setup, low, free = await self._context()
        return await overview.report(self.session, rng, setup=setup, low_threshold=low, free_threshold=free)

    async def sales(self, rng: DateRange) -> dict[str, Any]:
        return await sales.report(self.session, rng)

    async def products(self, rng: DateRange) -> dict[str, Any]:
        return await products.report(self.session, rng)

    async def traffic(self, rng: DateRange) -> dict[str, Any]:
        return await traffic.report(self.session, rng)

    async def funnel(self, rng: DateRange) -> dict[str, Any]:
        return await traffic.funnel_report(self.session, rng)

    async def behavior(self, rng: DateRange) -> dict[str, Any]:
        return await traffic.behavior_report(self.session, rng)

    async def performance(self, rng: DateRange) -> dict[str, Any]:
        return await traffic.performance_report(self.session, rng)

    async def customers(self, rng: DateRange) -> dict[str, Any]:
        return await customers.report(self.session, rng)

    async def promotions(self, rng: DateRange) -> dict[str, Any]:
        return await promotions.report(self.session, rng)

    async def inventory(self) -> dict[str, Any]:
        _, low, _ = await self._context()
        return await inventory.inventory_report(self.session, low)

    async def catalog(self) -> dict[str, Any]:
        return await inventory.catalog_report(self.session)

    async def suggestions(self, rng: DateRange) -> dict[str, Any]:
        setup, low, free = await self._context()
        now = datetime.now(timezone.utc)
        items = await insights.suggestions(self.session, rng, setup=setup, low_threshold=low, free_threshold=free, now=now)
        return {
            "range": c.range_info(rng), "items": items, "counts": {sev: sum(1 for i in items if i["severity"] == sev) for sev in SEVERITIES},
            "generated_at": now.isoformat(),
        }

    async def export(self, kind: str, rng: DateRange) -> tuple[str, str]:
        """(file name, CSV text) for one of `exports.EXPORTS`."""
        builders = {
            "sales": self.sales, "products": self.products, "traffic": self.traffic, "funnel": self.funnel, "customers": self.customers,
            "promotions": self.promotions,
        }
        if kind in builders:
            report = await builders[kind](rng)
        elif kind == "inventory":
            report = await self.inventory()
        else:
            report = await self.catalog()
        stem, text = exports.render(kind, report)
        return f"{stem}-{rng.start.isoformat()}-to-{rng.end.isoformat()}.csv" if kind not in ("inventory", "catalog") else f"{stem}.csv", text
