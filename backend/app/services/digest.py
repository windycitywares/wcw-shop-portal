"""The owner's weekly email: last week against the week before, the best sellers, and what to do next."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import emailtext
from app.domain.timeutil import DateRange, to_store_time
from app.services import emails, jobstate
from app.services.reports import products, sales, traffic
from app.services.reports.service import ReportService
from app.services.settings import SettingsService

SEND_HOUR = 7  # store time, on Mondays


def change_text(now: float | None, before: float | None) -> str:
    if now is None or before is None or not before:
        return ""
    pct = (now - before) / abs(before) * 100
    return f"  ({pct:+.0f}%)"


def kpi_rows(sold: dict[str, Any], before: dict[str, Any], visits: dict[str, Any], visits_before: dict[str, Any]) -> list[tuple[str, str]]:
    money = emailtext.money
    conv = visits["conversion_rate"]
    return [
        ("Net revenue", money(sold["net"]) + change_text(sold["net"], before["net"])),
        ("Orders", f"{sold['orders']}" + change_text(sold["orders"], before["orders"])),
        ("Average order", (money(sold["aov"]) if sold["aov"] is not None else "-") + change_text(sold["aov"], before["aov"])),
        ("Visitors", f"{visits['visitors']}" + change_text(visits["visitors"], visits_before["visitors"])),
        ("Conversion rate", f"{conv * 100:.1f}%" if conv is not None else "-"),
        ("Refunds", money(sold["refunds"])),
    ]


class DigestJob:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self, now: datetime | None = None, force: bool = False) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        settings = await SettingsService(self.session).load()
        recipients = settings.digest.recipients or ([settings.general.order_alert_email] if settings.general.order_alert_email else [])
        if not settings.digest.enabled or not recipients:
            return {"sent": 0, "reason": "off" if not settings.digest.enabled else "no recipients"}
        local = to_store_time(now)
        if not force and (local.weekday() != 0 or local.hour < SEND_HOUR):
            return {"sent": 0, "reason": "not due"}
        if not await jobstate.claim(self.session, "digest", local.date().isoformat()):
            return {"sent": 0, "reason": "already sent"}
        last_sunday = local.date() - timedelta(days=local.weekday() + 1)
        rng = DateRange(last_sunday - timedelta(days=6), last_sunday)
        sold, before = await sales.totals(self.session, rng), await sales.totals(self.session, rng.previous())
        visits, visits_before = await traffic.totals(self.session, rng), await traffic.totals(self.session, rng.previous())
        best = [p for p in await products.table(self.session, rng) if p["units"] > 0][:3]
        advice = [i for i in (await ReportService(self.session).suggestions(rng))["items"] if i["severity"] in ("critical", "warning", "opportunity")][:3]
        sections: list[tuple[str, list[str]]] = []
        if best:
            sections.append(("Best sellers", [f"{p['title']}: {p['units']} sold, {emailtext.money(p['merchandise'])}" for p in best]))
        if advice:
            sections.append(("What to do next", [f"{i['title']}" + (f" - {i['action']}" if i.get("action") else "") for i in advice]))
        ctx = {
            "subject": f"Your week at WindyCityWares: {emailtext.money(sold['net'])} from {sold['orders']} order{'s' if sold['orders'] != 1 else ''}",
            "intro": f"Here is how the shop did from {emailtext.long_date(rng.start)} to {emailtext.long_date(rng.end)}, compared with the week before.",
            "kpis": kpi_rows(sold, before, visits, visits_before), "sections": sections, "link": emails.site_link("/admin"),
        }
        rows = [emails.enqueue(self.session, "digest", to, ctx, locale="en", related_type="digest") for to in recipients[:10]]
        await self.session.commit()
        await emails.deliver(self.session, rows)
        return {"sent": len(rows), "week_ending": rng.end.isoformat()}
