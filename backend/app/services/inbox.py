"""The contact-form inbox: read messages, mark them answered, keep notes."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.user import User
from app.repositories.account import ContactRepository
from app.schemas.account import MessageOut, MessageUpdate
from app.schemas.common import Page


class InboxService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ContactRepository(session)

    async def search(self, *, status: str | None, q: str | None, page: int, page_size: int) -> Page[MessageOut]:
        rows, total = await self.repo.search(status=status, q=q, page=page, page_size=page_size)
        return Page[MessageOut](items=[MessageOut.model_validate(m) for m in rows], total=total, page=page, page_size=page_size)

    async def counts(self) -> dict[str, int]:
        have = await self.repo.counts()
        return {s: have.get(s, 0) for s in ("new", "answered", "archived")}

    async def update(self, message_id: int, data: MessageUpdate, actor: User) -> MessageOut:
        message = await self.repo.get(message_id)
        if message is None:
            raise NotFoundError("Message not found")
        changes = data.model_dump(exclude_unset=True)
        if "admin_note" in changes:
            message.admin_note = (changes["admin_note"] or "").strip() or None
        if changes.get("status"):
            if changes["status"] != message.status:
                message.handled_by_id = actor.id if changes["status"] != "new" else None
                message.handled_at = datetime.now(timezone.utc) if changes["status"] != "new" else None
            message.status = changes["status"]
        await self.session.commit()
        return MessageOut.model_validate(message)
