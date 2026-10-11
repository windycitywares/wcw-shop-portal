from sqlalchemy import func, select, text

from app.models.category import Category
from app.models.product import Product
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    model = Category

    async def next_id(self) -> int:
        """Reserve the id up front so the materialized path can be written in one INSERT."""
        return (await self.session.execute(text("SELECT nextval('categories_id_seq')"))).scalar_one()

    async def list_all(self, active_only: bool = False) -> list[Category]:
        stmt = select(Category).order_by(func.nlevel(Category.path), Category.sort_order, Category.name)
        if active_only:
            stmt = stmt.where(Category.is_active.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())

    async def ancestors(self, path: str, include_self: bool = True) -> list[Category]:
        stmt = select(Category).where(Category.path.op("@>")(path)).order_by(func.nlevel(Category.path))
        rows = list((await self.session.execute(stmt)).scalars().all())
        return rows if include_self else [c for c in rows if c.path != path]

    async def children(self, parent_id: int | None, active_only: bool = False) -> list[Category]:
        cond = Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id
        stmt = select(Category).where(cond).order_by(Category.sort_order, Category.name)
        if active_only:
            stmt = stmt.where(Category.is_active.is_(True))
        return list((await self.session.execute(stmt)).scalars().all())

    async def find_child_by_name(self, parent_id: int | None, name: str) -> Category | None:
        cond = Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id
        stmt = select(Category).where(cond, func.lower(Category.name) == name.strip().lower()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def has_children(self, category_id: int) -> bool:
        return await self.count(Category.parent_id == category_id) > 0

    async def has_products(self, category_id: int) -> bool:
        stmt = select(func.count()).select_from(Product).where(Product.category_id == category_id)
        return (await self.session.execute(stmt)).scalar_one() > 0

    async def rewrite_subtree_paths(self, old_path: str, new_path: str, node_id: int) -> None:
        """Re-root every descendant of `old_path` under `new_path` (one UPDATE, any depth)."""
        await self.session.execute(
            text(
                "UPDATE categories "
                "SET path = text2ltree(CAST(:new_path AS TEXT)) || subpath(path, :old_level) "
                "WHERE path <@ text2ltree(CAST(:old_path AS TEXT)) AND id <> :node_id"
            ),
            {
                "new_path": new_path,
                "old_path": old_path,
                "old_level": old_path.count(".") + 1,
                "node_id": node_id,
            },
        )
