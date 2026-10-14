"""Store visit events from the storefront (only ever called for visitors who accepted analytics).

What is kept: a random visit id and a random browser id, the page, product, search term and cart value of
each event, and coarse labels (device, browser, where the visit came from). What is not: IP addresses, the
raw user agent, query strings, or anything that identifies a person.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain import channels, tracking
from app.domain.timeutil import store_today
from app.models.analytics import AnalyticsEvent
from app.models.product import Product
from app.schemas.analytics import LandingIn, TrackIn
from app.services.settings import SettingsService

UPSERT_SESSION = text("""
INSERT INTO analytics_sessions (id, visitor_id, landing_path, referrer_host, channel, utm_source, utm_medium, utm_campaign,
                                device, browser, os, locale, is_new_visitor, page_views, event_count)
SELECT :id, :visitor_id, :landing_path, :referrer_host, :channel, :utm_source, :utm_medium, :utm_campaign,
       :device, :browser, :os, :locale, NOT EXISTS (SELECT 1 FROM analytics_sessions s WHERE s.visitor_id = :visitor_id), :page_views, :events
ON CONFLICT (id) DO UPDATE SET last_seen_at = now(),
    page_views = analytics_sessions.page_views + EXCLUDED.page_views,
    event_count = analytics_sessions.event_count + EXCLUDED.event_count
WHERE analytics_sessions.visitor_id = EXCLUDED.visitor_id
RETURNING id
""")

UPSERT_CONSENT = text("""
INSERT INTO consent_daily (day, accepted, declined) VALUES (:day, :accepted, :declined)
ON CONFLICT (day) DO UPDATE SET accepted = consent_daily.accepted + EXCLUDED.accepted, declined = consent_daily.declined + EXCLUDED.declined
""")


def own_hosts() -> tuple[str, ...]:
    """The shop's own host and its parent domain, so a click from our own site isn't counted as a referral."""
    host = urlsplit(get_settings().site_url).hostname or ""
    parts = host.split(".")
    return tuple(dict.fromkeys(h for h in (host, ".".join(parts[-2:]) if len(parts) > 2 else "") if h))


def _short(value: str | None, limit: int) -> str | None:
    value = " ".join((value or "").split())[:limit]
    return value or None


class TrackingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(self, batch: TrackIn, user_agent: str | None) -> int:
        """Store the batch. Returns how many events were kept (0 for crawlers, switched-off analytics or junk)."""
        if not get_settings().analytics_accept_bots and channels.is_bot(user_agent):
            return 0
        if not (await SettingsService(self.session).load()).analytics.enabled:
            return 0
        rows = [row for row in (tracking.clean_event(e.model_dump()) for e in batch.events) if row is not None]
        if not rows:
            return 0
        landing = batch.landing or LandingIn()
        channel = channels.classify_channel(
            channels.referrer_host(landing.referrer), landing.utm_source, landing.utm_medium, own_hosts()
        )
        device, browser, os_name = channels.parse_user_agent(user_agent)
        claimed = await self.session.execute(UPSERT_SESSION, {
            "id": batch.session_id, "visitor_id": batch.visitor_id, "landing_path": tracking.clean_path(landing.path),
            "referrer_host": channels.referrer_host(landing.referrer), "channel": channel,
            "utm_source": _short(landing.utm_source, 100), "utm_medium": _short(landing.utm_medium, 100),
            "utm_campaign": _short(landing.utm_campaign, 150), "device": device, "browser": browser, "os": os_name,
            "locale": landing.locale, "page_views": sum(1 for r in rows if r["type"] == "page_view"), "events": len(rows),
        })
        if claimed.first() is None:  # this visit id already belongs to another browser
            await self.session.rollback()
            return 0
        wanted = {r["product_id"] for r in rows if r["product_id"] is not None}
        known = set((await self.session.execute(select(Product.id).where(Product.id.in_(wanted)))).scalars()) if wanted else set()
        await self.session.execute(insert(AnalyticsEvent), [
            {"session_id": batch.session_id, "type": r["type"], "path": r["path"],
             "product_id": r["product_id"] if r["product_id"] in known else None, "value": r["value"], "data": r["data"]}
            for r in rows
        ])
        await self.session.commit()
        return len(rows)

    async def consent(self, accepted: bool) -> None:
        """Count a banner decision. Only a daily total is kept, never who decided."""
        await self.session.execute(UPSERT_CONSENT, {"day": store_today(), "accepted": int(accepted), "declined": int(not accepted)})
        await self.session.commit()
