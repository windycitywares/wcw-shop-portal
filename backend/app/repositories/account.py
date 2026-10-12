from datetime import datetime

from sqlalchemy import select, update

from app.models.account import Address, ContactMessage, PasswordResetToken
from app.repositories.base import BaseRepository


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
