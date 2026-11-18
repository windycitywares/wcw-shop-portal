"""Supplier logins: an account with role "supplier", tied to a supplier name (as written on orders) and to the external
shops it may see. Admins create and change them; a supplier sees only orders whose supplier is theirs."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.domain import channels as ch
from app.models.user import User
from app.services import audit
from app.services.auth import UserService
from app.schemas.user import UserCreate


def _channels(values: list[str]) -> list[str]:
    try:
        out = ch.clean(values)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc
    if not out:
        raise ValidationFailedError("Choose at least one shop the supplier may see")
    return out


def _name(value: str) -> str:
    name = " ".join(value.split())
    if not name:
        raise ValidationFailedError("Enter the supplier's name as it is written on orders")
    return name[:200]


class SupplierAccounts:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self) -> list[User]:
        return list((await self.session.execute(
            select(User).where(User.role == UserRole.SUPPLIER).order_by(User.supplier_name, User.email))).scalars())

    async def create(self, actor: User, *, email: str, password: str, full_name: str | None, supplier_name: str,
                     channels: list[str]) -> User:
        name, shops = _name(supplier_name), _channels(channels)
        user = await UserService(self.session).create(
            UserCreate(email=email, password=password, full_name=full_name, role=UserRole.SUPPLIER))
        user.supplier_name, user.supplier_channels = name, shops
        audit.record(self.session, actor, "supplier_login.create", "user", user.id,
                     f"Supplier login {user.email} for {name} ({', '.join(shops)})")
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, actor: User, user_id: int, *, supplier_name: str | None, channels: list[str] | None) -> User:
        user = await self.session.get(User, user_id)
        if user is None or user.role != UserRole.SUPPLIER:
            raise NotFoundError("Supplier login not found")
        if supplier_name is not None:
            user.supplier_name = _name(supplier_name)
        if channels is not None:
            user.supplier_channels = _channels(channels)
        audit.record(self.session, actor, "supplier_login.update", "user", user.id,
                     f"Supplier login {user.email}: {user.supplier_name} ({', '.join(user.supplier_channels)})")
        await self.session.commit()
        await self.session.refresh(user)
        return user
