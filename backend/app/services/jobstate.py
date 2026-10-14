"""Remember that a periodic job already did its work for a day or week, so a repeated cron run never does it twice."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Atomic: inserts the marker or moves it forward, and only reports success when it actually changed.
CLAIM = text("""
INSERT INTO store_settings (key, value) VALUES (CAST(:key AS varchar), jsonb_build_object('last', CAST(:token AS text)))
ON CONFLICT (key) DO UPDATE SET value = jsonb_build_object('last', CAST(:token AS text)), updated_at = now()
WHERE store_settings.value->>'last' IS DISTINCT FROM CAST(:token AS text)
RETURNING 1
""")


async def claim(session: AsyncSession, job: str, token: str) -> bool:
    """True the first time `token` (a date, week id...) is seen for `job`. Call inside the transaction that does the work:
    a failure rolls the claim back, so the next run tries again. Settings groups never start with "job:", so these rows are ignored there."""
    return (await session.execute(CLAIM, {"key": f"job:{job}", "token": token})).first() is not None
