"""Contacts: the superset of customers, users and everyone else we've met.

A Contact is created (or refreshed) whenever the shop learns about someone: sign-up, an order, a newsletter
subscription, a contact-form message, a stock-alert request. Email is the key; the first source to claim an
address keeps its name/phone, the rest just make sure the row exists.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact


class ContactService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        email: str,
        *,
        full_name: str | None = None,
        phone: str | None = None,
        source: str = "import",
        user_id: int | None = None,
        marketing_opt_in: bool | None = None,
    ) -> Contact:
        email = email.strip().lower()
        row = (await self.session.execute(select(Contact).where(Contact.email == email))).scalar_one_or_none()
        created = False
        changed = False
        if row is None:
            row = Contact(
                email=email, full_name=full_name, phone=phone, source=source,
                user_id=user_id, marketing_opt_in=bool(marketing_opt_in),
            )
            self.session.add(row)
            await self.session.flush()
            created = True
        else:
            if full_name and not row.full_name:
                row.full_name = full_name
                changed = True
            if phone and not row.phone:
                row.phone = phone
                changed = True
            if user_id is not None and row.user_id is None:
                row.user_id = user_id
                changed = True
            if marketing_opt_in is True and not row.marketing_opt_in:
                row.marketing_opt_in = True
                changed = True
        return row
