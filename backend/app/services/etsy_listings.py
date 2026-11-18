"""Etsy listings → the shop, one way. Etsy is the source of truth: every pass overwrites the Etsy columns and never touches
the team's internal_* columns. A listing Etsy no longer returns is marked `removed`, not deleted, so old orders still link."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import etsy_listing
from app.models.etsy import EtsyListing
from app.services import etsy_client
from app.services.etsy_client import EtsyError
from app.services.etsy_connection import EtsyConnectionService

PAGE = 100
EVERY = timedelta(minutes=15)  # the job runs every few minutes; a full pass is this often


class EtsyListingSync:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(self, force: bool = False) -> dict[str, Any]:
        conn = await EtsyConnectionService(self.session).row()
        if not (conn.access_token and conn.etsy_shop_id):
            return {"skipped": "not connected"}
        now = datetime.now(timezone.utc)
        if not force and conn.listings_synced_at and now - conn.listings_synced_at < EVERY:
            return {"skipped": "not due"}
        service = EtsyConnectionService(self.session)
        try:
            key, token = await service.access_token()
            seen: set[int] = set()
            created = updated = 0
            for state in etsy_listing.STATES:
                offset = 0
                while True:
                    data = await etsy_client.get(
                        f"/shops/{conn.etsy_shop_id}/listings", api_key=key, access_token=token,
                        params={"state": state, "limit": PAGE, "offset": offset, "includes": "Images,Inventory"})
                    results = data.get("results") or []
                    for raw in results:
                        c, u = await self._upsert(etsy_listing.parse({**raw, "state": raw.get("state") or state}), now)
                        seen.add(int(raw["listing_id"]))
                        created, updated = created + c, updated + u
                    offset += PAGE
                    if len(results) < PAGE:
                        break
            removed = await self._mark_removed(seen)
        except EtsyError as exc:
            await self.session.rollback()
            await service.fail(f"Listing sync: {exc}")
            return {"error": str(exc)[:200]}
        conn = await service.row()
        conn.listings_synced_at, conn.last_error, conn.last_error_at = now, None, None
        await self.session.commit()
        return {"created": created, "updated": updated, "removed": removed, "total": len(seen)}

    async def _upsert(self, fields: dict[str, Any], now: datetime) -> tuple[int, int]:
        row = (await self.session.execute(
            select(EtsyListing).where(EtsyListing.etsy_listing_id == fields["etsy_listing_id"]))).scalar_one_or_none()
        if row is None:
            self.session.add(EtsyListing(**fields, synced_at=now))
            return 1, 0
        for k, v in fields.items():
            setattr(row, k, v)
        row.synced_at = now
        return 0, 1

    async def _mark_removed(self, seen: set[int]) -> int:
        if not seen:  # an empty answer is more likely a problem than a shop with nothing in it
            return 0
        rows = (await self.session.execute(
            select(EtsyListing).where(EtsyListing.etsy_listing_id.not_in(seen), EtsyListing.state != "removed"))).scalars().all()
        for r in rows:
            r.state = "removed"
        return len(rows)


async def search(session: AsyncSession, q: str | None, state: str | None, page: int, page_size: int,
                 supplier: str | None = None) -> tuple[list[EtsyListing], int]:
    cond = []
    if supplier == "__none__":
        cond.append(EtsyListing.internal_supplier.is_(None))
    elif supplier:
        cond.append(func.lower(EtsyListing.internal_supplier) == supplier.strip().lower())
    if q:
        like = f"%{q.strip().lower()}%"
        cond.append(or_(func.lower(EtsyListing.title).like(like), func.lower(cast(EtsyListing.skus, Text)).like(like)))
    if state:
        cond.append(EtsyListing.state == state)
    total = (await session.execute(select(func.count()).select_from(EtsyListing).where(*cond))).scalar_one()
    rows = (await session.execute(
        select(EtsyListing).where(*cond).order_by(EtsyListing.title).limit(page_size).offset((page - 1) * page_size))).scalars().all()
    return list(rows), total
