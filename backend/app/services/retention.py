"""Delete old data: analytics are kept for the number of days set in Settings, and finished emails for 120 days.

Orders, customers and reviews are never deleted here. Work is done in small batches so it never blocks the shop.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings import SettingsService

BATCH = 5000
MAX_BATCHES = 10  # per table per run; the next run continues
EMAIL_DAYS = 120

STEPS = (
    ("analytics_events", "DELETE FROM analytics_events WHERE id IN (SELECT id FROM analytics_events WHERE created_at < :cutoff ORDER BY id LIMIT :n)"),
    ("analytics_sessions", "DELETE FROM analytics_sessions WHERE id IN (SELECT id FROM analytics_sessions WHERE started_at < :cutoff LIMIT :n)"),
    ("carts", "DELETE FROM carts WHERE id IN (SELECT id FROM carts WHERE last_activity_at < :cutoff LIMIT :n)"),
    ("email_outbox", "DELETE FROM email_outbox WHERE id IN (SELECT id FROM email_outbox WHERE status <> 'queued' AND created_at < :mail_cutoff LIMIT :n)"),
)


async def purge(session: AsyncSession, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    days = (await SettingsService(session).load()).analytics.retention_days
    params = {"cutoff": now - timedelta(days=days), "mail_cutoff": now - timedelta(days=EMAIL_DAYS), "n": BATCH}
    deleted: dict[str, int] = {}
    for table, sql in STEPS:
        total = 0
        for _ in range(MAX_BATCHES):
            result = await session.execute(text(sql), params)
            await session.commit()
            total += result.rowcount or 0
            if (result.rowcount or 0) < BATCH:
                break
        deleted[table] = total
    return deleted
