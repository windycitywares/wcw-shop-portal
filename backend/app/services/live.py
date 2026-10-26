"""Reading live events (written by app/core/live_events.py) for the admin's live updates."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class LiveEventService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def since(self, after: int | None, permissions: list[str], limit: int = 50) -> dict[str, Any]:
        last = (await self.session.execute(text("SELECT COALESCE(max(id), 0) FROM live_events"))).scalar_one()
        if after is None or after > last:  # first call, or the table was emptied / replaced (Test mode switch)
            return {"events": [], "last_id": int(last)}
        rows = (await self.session.execute(
            text("SELECT id, kind, ref_id, title, detail, href, created_at FROM live_events "
                 "WHERE id > :after AND permission = ANY(:perms) ORDER BY id LIMIT :n"),
            {"after": after, "perms": permissions, "n": limit},
        )).mappings().all()
        events = [{**dict(r), "at": r["created_at"]} for r in rows]
        for e in events:
            e.pop("created_at", None)
        # Resume after the newest row looked at, even one this person may not see, so it isn't read again.
        newest = events[-1]["id"] if len(events) == limit else max(int(last), events[-1]["id"] if events else 0)
        return {"events": events, "last_id": newest}
