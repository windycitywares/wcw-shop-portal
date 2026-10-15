"""Contact inbox: read, triage, note and answer messages from the Contact page.

Replies go through the email outbox (so a failed send is retried by the cron) and are sent at once when possible.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.account import ContactMessage, ContactReply
from app.models.commerce import EmailOutbox
from app.models.order import Order
from app.models.user import User
from app.schemas.inbox import (
    CustomerOrder, EarlierMessage, InboxItemOut, InboxListOut, InboxMessageOut, InboxReplyIn, InboxReplyOut, InboxUpdateIn, ReplyOut,
)
from app.services import audit, emails
from app.utils.text import escape_like

STATUSES = ("new", "open", "replied", "closed", "spam")
ACTIVE = ("new", "open")  # the default view: still needs a person
PREVIEW = 160


def preview(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= PREVIEW else flat[: PREVIEW - 1].rstrip() + "…"


def quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.strip().splitlines())


def reply_text(body: str, staff: User, original: ContactMessage) -> str:
    """The email the customer receives: the reply, a sign-off, and their message quoted underneath."""
    settings = get_settings()
    first = (staff.full_name or "").split(" ")[0] if staff.full_name else ""
    sign = f"{first}, {settings.mail_from_name}" if first else settings.mail_from_name
    when = original.created_at.strftime("%b %d, %Y") if original.created_at else ""
    return f"{body.strip()}\n\n— {sign}\n{settings.site_url}\n\nOn {when} you wrote:\n{quote(original.message)}\n"


class InboxService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get(self, message_id: int) -> ContactMessage:
        msg = await self.session.get(ContactMessage, message_id)
        if msg is None:
            raise NotFoundError("Message not found")
        return msg

    async def counts(self) -> dict[str, int]:
        rows = (await self.session.execute(select(ContactMessage.status, func.count()).group_by(ContactMessage.status))).all()
        found = {s: 0 for s in STATUSES}
        found.update({s: n for s, n in rows})
        found["active"] = found["new"] + found["open"]
        found["all"] = sum(found[s] for s in STATUSES if s != "spam")
        return found

    async def list(self, status: str | None, q: str | None, page: int, page_size: int) -> InboxListOut:
        replies = (
            select(ContactReply.message_id, func.count().label("n")).group_by(ContactReply.message_id).subquery()
        )
        conds = []
        if status in (None, "active"):
            conds.append(ContactMessage.status.in_(ACTIVE))
        elif status == "all":
            conds.append(ContactMessage.status != "spam")
        else:
            conds.append(ContactMessage.status == status)
        if q:
            like = f"%{escape_like(q.strip())}%"
            conds.append(or_(
                ContactMessage.email.ilike(like), ContactMessage.name.ilike(like), ContactMessage.subject.ilike(like),
                ContactMessage.message.ilike(like), ContactMessage.order_number.ilike(like),
            ))
        total = (await self.session.execute(select(func.count()).select_from(ContactMessage).where(*conds))).scalar_one()
        # new first, then newest
        rows = (await self.session.execute(
            select(ContactMessage, func.coalesce(replies.c.n, 0))
            .outerjoin(replies, replies.c.message_id == ContactMessage.id)
            .where(*conds)
            .order_by(case((ContactMessage.status == "new", 0), else_=1), ContactMessage.created_at.desc(), ContactMessage.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )).all()
        items = [
            InboxItemOut(
                id=m.id, name=m.name, email=m.email, subject=m.subject, preview=preview(m.message), order_number=m.order_number,
                status=m.status, replies=n, created_at=m.created_at,
            )
            for m, n in rows
        ]
        return InboxListOut(items=items, total=total, page=page, page_size=page_size, counts=await self.counts())

    async def detail(self, message_id: int, *, mark_read: bool = True) -> InboxMessageOut:
        msg = await self._get(message_id)
        if mark_read and msg.status == "new":
            msg.status = "open"
            await self.session.commit()
            await self.session.refresh(msg)
        replies = (await self.session.execute(
            select(ContactReply).where(ContactReply.message_id == msg.id).order_by(ContactReply.created_at, ContactReply.id)
        )).scalars().all()
        email = msg.email.lower()
        earlier = (await self.session.execute(
            select(ContactMessage).where(func.lower(ContactMessage.email) == email, ContactMessage.id != msg.id)
            .order_by(ContactMessage.created_at.desc()).limit(10)
        )).scalars().all()
        orders = (await self.session.execute(
            select(Order).where(func.lower(Order.email) == email).order_by(Order.id.desc()).limit(10)
        )).scalars().all()
        order_id = None
        if msg.order_number:
            order_id = (await self.session.execute(select(Order.id).where(func.upper(Order.number) == msg.order_number.strip().upper()).limit(1))).scalar_one_or_none()
        handler = await self.session.get(User, msg.handled_by_id) if msg.handled_by_id else None
        return InboxMessageOut(
            id=msg.id, name=msg.name, email=msg.email, subject=msg.subject, message=msg.message, order_number=msg.order_number,
            order_id=order_id, locale=msg.locale, status=msg.status, staff_note=msg.staff_note, emailed=msg.emailed,
            signed_in=msg.user_id is not None, handled_at=msg.handled_at, handled_by_email=handler.email if handler else None,
            created_at=msg.created_at,
            replies=[ReplyOut.model_validate(r) for r in replies],
            earlier=[EarlierMessage(id=e.id, subject=e.subject, status=e.status, created_at=e.created_at) for e in earlier],
            orders=[
                CustomerOrder(id=o.id, number=o.number, status=getattr(o.status, "value", str(o.status)), grand_total=o.grand_total, placed_at=o.placed_at)
                for o in orders
            ],
        )

    def _handled(self, msg: ContactMessage, user: User) -> None:
        msg.handled_at = datetime.now(timezone.utc)
        msg.handled_by_id = user.id

    async def update(self, message_id: int, data: InboxUpdateIn, user: User) -> InboxMessageOut:
        msg = await self._get(message_id)
        changes = []
        if data.status is not None and data.status != msg.status:
            changes.append(f"marked {data.status}")
            msg.status = data.status
            if data.status in ("closed", "spam"):
                self._handled(msg, user)
        if "staff_note" in data.model_fields_set:
            note = (data.staff_note or "").strip() or None
            if note != msg.staff_note:
                msg.staff_note = note
                changes.append("edited the note")
        if changes:
            audit.record(self.session, user, "inbox.update", "contact_message", msg.id, f"Message from {msg.email}: {', '.join(changes)}")
            await self.session.commit()
        return await self.detail(msg.id, mark_read=False)

    async def reply(self, message_id: int, data: InboxReplyIn, user: User) -> InboxReplyOut:
        msg = await self._get(message_id)
        if msg.status == "spam":
            raise ValidationFailedError("This message is marked as spam. Move it back to the inbox before replying.")
        subject = msg.subject if msg.subject.lower().startswith("re:") else f"Re: {msg.subject}"
        row = EmailOutbox(
            to_email=msg.email.strip().lower(), kind="contact_reply", subject=subject[:300], body_text=reply_text(data.body, user, msg),
            body_html=None, locale=msg.locale, related_type="contact", related_id=msg.id,
            send_after=datetime.now(timezone.utc), status="queued", attempts=0,
        )
        self.session.add(row)
        reply = ContactReply(message_id=msg.id, author_id=user.id, author_email=user.email, body=data.body)
        self.session.add(reply)
        msg.status = "closed" if data.close else "replied"
        self._handled(msg, user)
        audit.record(self.session, user, "inbox.reply", "contact_message", msg.id, f"Replied to {msg.email}: {msg.subject}")
        await self.session.commit()
        await emails.deliver(self.session, [row])  # a failed send stays queued for the cron to retry
        reply.emailed = row.status == "sent"
        await self.session.commit()
        return InboxReplyOut(message=await self.detail(msg.id, mark_read=False), emailed=reply.emailed)

    async def delete(self, message_id: int, user: User) -> None:
        msg = await self._get(message_id)
        audit.record(self.session, user, "inbox.delete", "contact_message", msg.id, f"Deleted message from {msg.email}: {msg.subject}")
        await self.session.delete(msg)
        await self.session.commit()

    async def unanswered(self) -> int:
        return (await self.session.execute(select(func.count()).select_from(ContactMessage).where(ContactMessage.status.in_(ACTIVE)))).scalar_one()
