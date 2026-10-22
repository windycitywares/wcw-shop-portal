"""The newsletter list as the shop owner sees it: who joined, who left, and how to manage them.

Rows made only so a service email (cart reminder, order update) can carry an unsubscribe link are not
subscribers and are never listed. Staff can add an address, take one off the list, or delete the row;
they cannot sign someone back up, because only the person can agree to marketing email again.
Staff can also pause someone: they stay subscribed but campaigns skip them until resumed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.domain.contacts import SERVICE_ONLY_SOURCES
from app.domain.csvsafe import to_csv
from app.models.user import NewsletterSubscriber, User
from app.schemas.subscribers import SubscriberCounts, SubscriberList, SubscriberOut
from app.services import audit
from app.services.auth import NewsletterService

STATUSES = ("all", "subscribed", "paused", "unsubscribed")
_ORDERED = text(
    "SELECT lower(email) FROM orders WHERE status <> 'cancelled' AND lower(email) = ANY(CAST(:emails AS text[]))"
)


def _real():
    return NewsletterSubscriber.source.notin_(SERVICE_ONLY_SOURCES)


class SubscriberService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _filters(self, q: str | None, status: str):
        conds = [_real()]
        if status == "subscribed":
            conds.append(NewsletterSubscriber.unsubscribed_at.is_(None))
        elif status == "paused":
            conds += [NewsletterSubscriber.unsubscribed_at.is_(None), NewsletterSubscriber.paused_at.is_not(None)]
        elif status == "unsubscribed":
            conds.append(NewsletterSubscriber.unsubscribed_at.is_not(None))
        if q and q.strip():
            like = "%" + q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            conds.append(or_(func.lower(NewsletterSubscriber.email).like(like, escape="\\")))
        return conds

    async def _rows(self, q, status, offset: int | None = None, limit: int | None = None) -> list[SubscriberOut]:
        stmt = select(NewsletterSubscriber).where(*self._filters(q, status)).order_by(NewsletterSubscriber.id.desc())
        if limit is not None:
            stmt = stmt.offset(offset or 0).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        ordered: set[str] = set()
        if rows:
            ordered = {r[0] for r in (await self.session.execute(_ORDERED, {"emails": [r.email.lower() for r in rows]})).all()}
        return [
            SubscriberOut(
                id=r.id, email=r.email, locale=r.locale, source=r.source, subscribed=r.unsubscribed_at is None,
                subscribed_at=r.created_at, unsubscribed_at=r.unsubscribed_at,
                paused=r.unsubscribed_at is None and r.paused_at is not None, paused_at=r.paused_at, welcome_coupon=r.welcome_coupon,
                has_ordered=r.email.lower() in ordered,
            )
            for r in rows
        ]

    async def counts(self) -> SubscriberCounts:
        total, left, paused = (await self.session.execute(
            select(
                func.count(), func.count(NewsletterSubscriber.unsubscribed_at),
                func.count().filter(NewsletterSubscriber.unsubscribed_at.is_(None), NewsletterSubscriber.paused_at.is_not(None)),
            ).where(_real())
        )).one()
        return SubscriberCounts(all=total, subscribed=total - left, paused=paused, unsubscribed=left)

    async def list(self, q: str | None, status: str, page: int, page_size: int) -> SubscriberList:
        total = (await self.session.execute(select(func.count()).select_from(NewsletterSubscriber).where(*self._filters(q, status)))).scalar_one()
        items = await self._rows(q, status, (page - 1) * page_size, page_size)
        return SubscriberList(items=items, total=total, page=page, page_size=page_size, counts=await self.counts())

    async def export_csv(self, q: str | None, status: str) -> str:
        rows = await self._rows(q, status)
        header = ["Email", "Status", "Language", "Joined from", "Joined", "Unsubscribed", "Has ordered", "Welcome code"]
        return to_csv(header, [
            (r.email, "paused" if r.paused else "subscribed" if r.subscribed else "unsubscribed", r.locale, r.source, r.subscribed_at, r.unsubscribed_at,
             r.has_ordered, r.welcome_coupon) for r in rows
        ])

    async def _get(self, subscriber_id: int) -> NewsletterSubscriber:
        row = (await self.session.execute(
            select(NewsletterSubscriber).where(NewsletterSubscriber.id == subscriber_id, _real())
        )).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Subscriber not found")
        return row

    async def add(self, email: str, locale: str, actor: User) -> SubscriberOut:
        """Sign up an address by hand (e.g. someone who asked in person). No welcome offer is sent."""
        existing = (await self.session.execute(
            select(NewsletterSubscriber).where(NewsletterSubscriber.email == email.strip().lower(), _real())
        )).scalar_one_or_none()
        if existing is not None and existing.unsubscribed_at is not None:
            raise ConflictError("This person unsubscribed. Only they can sign up again, from the form on the site.")
        row = await NewsletterService(self.session).add(email, locale, source="admin", welcome=False, commit=False)
        audit.record(self.session, actor, "subscriber.add", "subscriber", row.id, f"Added {row.email} to the newsletter")
        await self.session.commit()
        return next(r for r in await self._rows(row.email, "all") if r.id == row.id)

    async def unsubscribe(self, subscriber_id: int, actor: User) -> SubscriberOut:
        row = await self._get(subscriber_id)
        if row.unsubscribed_at is None:
            await NewsletterService(self.session).unsubscribe(row.unsubscribe_token)
            audit.record(self.session, actor, "subscriber.unsubscribe", "subscriber", row.id, f"Took {row.email} off the newsletter")
            await self.session.commit()
        return next(r for r in await self._rows(row.email, "all") if r.id == row.id)

    async def pause(self, subscriber_id: int, actor: User) -> SubscriberOut:
        """Hold campaign email for a while (a complaint, a bounce to check, a VIP handled by hand). Still subscribed."""
        row = await self._get(subscriber_id)
        if row.unsubscribed_at is not None:
            raise ConflictError("This person already unsubscribed, so there is nothing to pause.")
        if row.paused_at is None:
            row.paused_at = datetime.now(timezone.utc)
            audit.record(self.session, actor, "subscriber.pause", "subscriber", row.id, f"Paused campaign email to {row.email}")
            await self.session.commit()
        return next(r for r in await self._rows(row.email, "all") if r.id == row.id)

    async def resume(self, subscriber_id: int, actor: User) -> SubscriberOut:
        row = await self._get(subscriber_id)
        if row.paused_at is not None:
            row.paused_at = None
            audit.record(self.session, actor, "subscriber.resume", "subscriber", row.id, f"Resumed campaign email to {row.email}")
            await self.session.commit()
        return next(r for r in await self._rows(row.email, "all") if r.id == row.id)

    async def delete(self, subscriber_id: int, actor: User) -> None:
        """Remove the row for good (for a data-deletion request). The address can sign up again later."""
        row = await self._get(subscriber_id)
        audit.record(self.session, actor, "subscriber.delete", "subscriber", row.id, f"Deleted {row.email} from the newsletter list")
        await self.session.delete(row)
        await self.session.commit()
