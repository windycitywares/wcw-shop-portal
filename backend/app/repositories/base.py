"""Generic data-access layer. Repositories only talk to the database; business
rules (permissions, workflow) live in services."""

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base
from app.utils.text import slugify

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id_: int) -> ModelT | None:
        return await self.session.get(self.model, id_)

    async def get_by(self, **filters: Any) -> ModelT | None:
        stmt = select(self.model).filter_by(**filters).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count(self, *where: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        if where:
            stmt = stmt.where(*where)
        return (await self.session.execute(stmt)).scalar_one()

    def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)

    async def unique_slug(self, value: str, exclude_id: int | None = None, max_length: int = 200) -> str:
        """Return `value` slugified, with -2, -3 ... appended if already taken."""
        base = slugify(value, max_length=max_length - 6)
        slug_col = self.model.slug  # type: ignore[attr-defined]
        stmt = select(slug_col).where((slug_col == base) | slug_col.like(f"{base}-%"))
        if exclude_id is not None:
            stmt = stmt.where(self.model.id != exclude_id)  # type: ignore[attr-defined]
        taken = set((await self.session.execute(stmt)).scalars().all())
        if base not in taken:
            return base
        n = 2
        while f"{base}-{n}" in taken:
            n += 1
        return f"{base}-{n}"
