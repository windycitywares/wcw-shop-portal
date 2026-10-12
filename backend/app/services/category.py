from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.models.category import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import (
    CategoryCreate,
    CategoryDetail,
    CategoryNode,
    CategoryOut,
    CategoryReorder,
    CategoryUpdate,
)


def build_tree(categories: list[Category]) -> list[CategoryNode]:
    """Nest a flat list (ordered parents-first) into a tree."""
    # Build from the plain fields only — the ORM `children` relationship is lazy="raise".
    nodes = {c.id: CategoryNode(**CategoryOut.model_validate(c).model_dump()) for c in categories}
    roots: list[CategoryNode] = []
    for c in categories:
        node = nodes[c.id]
        parent = nodes.get(c.parent_id) if c.parent_id else None
        (parent.children if parent else roots).append(node)
    for node in nodes.values():
        node.children.sort(key=lambda n: (n.sort_order, n.name.lower()))
    roots.sort(key=lambda n: (n.sort_order, n.name.lower()))
    return roots


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CategoryRepository(session)

    async def tree(self, active_only: bool = True) -> list[CategoryNode]:
        return build_tree(await self.repo.list_all(active_only=active_only))

    async def get_or_404(self, category_id: int) -> Category:
        category = await self.repo.get(category_id)
        if not category:
            raise NotFoundError("Category not found")
        return category

    async def detail_by_slug(self, slug: str, active_only: bool = True) -> CategoryDetail:
        category = await self.repo.get_by(slug=slug)
        if not category or (active_only and not category.is_active):
            raise NotFoundError("Category not found")
        return await self.detail(category, active_only)

    async def detail(self, category: Category, active_only: bool = True) -> CategoryDetail:
        breadcrumb = await self.repo.ancestors(category.path)
        children = await self.repo.children(category.id, active_only=active_only)
        return CategoryDetail(
            **CategoryOut.model_validate(category).model_dump(),
            breadcrumb=[CategoryOut.model_validate(c) for c in breadcrumb],
            children=[CategoryOut.model_validate(c) for c in children],
        )

    async def create(self, data: CategoryCreate) -> Category:
        parent = await self.get_or_404(data.parent_id) if data.parent_id else None
        if data.slug:
            if await self.repo.get_by(slug=data.slug):
                raise ConflictError(f"Slug '{data.slug}' is already used")
            slug = data.slug
        else:
            slug = await self.repo.unique_slug(data.name)
        new_id = await self.repo.next_id()
        category = self.repo.add(
            Category(
                id=new_id,
                parent_id=parent.id if parent else None,
                path=f"{parent.path}.{new_id}" if parent else str(new_id),
                name=data.name.strip(),
                slug=slug,
                description=data.description,
                image_url=data.image_url,
                sort_order=data.sort_order,
                is_active=data.is_active,
                translations=data.translations,
            )
        )
        await self.session.commit()
        return category

    async def ensure_path(self, names: list[str]) -> Category | None:
        """Find or create a chain like ["Home", "Decor", "Vases"] (used by imports). Doesn't commit."""
        parent: Category | None = None
        for name in (n.strip() for n in names if n.strip()):
            found = await self.repo.find_child_by_name(parent.id if parent else None, name)
            if not found:
                new_id = await self.repo.next_id()
                found = self.repo.add(
                    Category(
                        id=new_id,
                        parent_id=parent.id if parent else None,
                        path=f"{parent.path}.{new_id}" if parent else str(new_id),
                        name=name,
                        slug=await self.repo.unique_slug(name),
                    )
                )
                await self.session.flush()
            parent = found
        return parent

    async def update(self, category_id: int, data: CategoryUpdate) -> Category:
        category = await self.get_or_404(category_id)
        changes = data.model_dump(exclude_unset=True)
        if "parent_id" in changes and changes["parent_id"] != category.parent_id:
            await self._move(category, changes.pop("parent_id"))
        else:
            changes.pop("parent_id", None)
        if changes.get("slug") and changes["slug"] != category.slug:
            if await self.repo.get_by(slug=changes["slug"]):
                raise ConflictError(f"Slug '{changes['slug']}' is already used")
        for field, value in changes.items():
            if value is None and field in ("name", "slug", "sort_order", "is_active", "translations"):
                continue
            setattr(category, field, value)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def reorder(self, data: CategoryReorder) -> list[CategoryNode]:
        """Apply a drag-and-drop result: new parent and position for each moved node."""
        for item in data.items:
            category = await self.get_or_404(item.id)
            if item.parent_id != category.parent_id:
                await self._move(category, item.parent_id)
            category.sort_order = item.sort_order
        await self.session.commit()
        return await self.tree(active_only=False)

    async def delete(self, category_id: int) -> None:
        category = await self.get_or_404(category_id)
        if await self.repo.has_children(category.id):
            raise ConflictError("Move or delete the sub-categories first")
        if await self.repo.has_products(category.id):
            raise ConflictError("This category still has products; move them first")
        await self.repo.delete(category)
        await self.session.commit()

    async def _move(self, category: Category, new_parent_id: int | None) -> None:
        old_path = category.path
        if new_parent_id is None:
            new_path = str(category.id)
        else:
            new_parent = await self.get_or_404(new_parent_id)
            if new_parent.id == category.id or new_parent.path.startswith(old_path + "."):
                raise ValidationFailedError("A category can't be moved inside itself")
            new_path = f"{new_parent.path}.{category.id}"
        await self.session.flush()
        await self.repo.rewrite_subtree_paths(old_path, new_path, category.id)
        # Descendants changed in SQL; make the session reload them on next access.
        for obj in list(self.session.identity_map.values()):
            if isinstance(obj, Category) and obj is not category:
                self.session.expire(obj)
        category.parent_id = new_parent_id
        category.path = new_path
        await self.session.flush()
