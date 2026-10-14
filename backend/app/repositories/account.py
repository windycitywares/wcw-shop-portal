from datetime import datetime

from sqlalchemy import func, or_, select, update

from app.models.account import Address, ContactMessage, PasswordResetToken
from app.repositories.base import BaseRepository
from app.utils.text import escape_like


class PasswordResetRepository(BaseRepository[PasswordResetToken]):
    model = PasswordResetToken

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        return await self.get_by(token_hash=token_hash)

    async def expire_all_for(self, user_id: int, now: datetime) -> None:
        """Mark every unused link for this user as used, so only the newest one works."""
        await self.session.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now)
        )


class AddressRepository(BaseRepository[Address]):
    model = Address

    async def list_for(self, user_id: int) -> list[Address]:
        stmt = (select(Address).where(Address.user_id == user_id)
                .order_by(Address.is_default.desc(), Address.created_at.desc(), Address.id.desc()))
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_for(self, user_id: int, address_id: int) -> Address | None:
        return await self.get_by(id=address_id, user_id=user_id)

    async def clear_default(self, user_id: int) -> None:
        await self.session.execute(
            update(Address).where(Address.user_id == user_id, Address.is_default.is_(True)).values(is_default=False)
        )


class ContactRepository(BaseRepository[ContactMessage]):
    model = ContactMessage

    async def search(self, *, status: str | None, q: str | None, page: int, page_size: int) -> tuple[list[ContactMessage], int]:
        where = []
        if status:
            where.append(ContactMessage.status == status)
        if q:
            like = f"%{escape_like(q.strip())}%"
            where.append(or_(ContactMessage.name.ilike(like), ContactMessage.email.ilike(like),
                             ContactMessage.subject.ilike(like), ContactMessage.message.ilike(like),
                             ContactMessage.order_number.ilike(like)))
        total = (await self.session.execute(select(func.count()).select_from(ContactMessage).where(*where))).scalar_one()
        stmt = (select(ContactMessage).where(*where).order_by(ContactMessage.created_at.desc(), ContactMessage.id.desc())
                .offset((page - 1) * page_size).limit(page_size))
        return list((await self.session.execute(stmt)).scalars().all()), total

    async def counts(self) -> dict[str, int]:
        rows = await self.session.execute(select(ContactMessage.status, func.count()).group_by(ContactMessage.status))
        return {status: n for status, n in rows.all()}
