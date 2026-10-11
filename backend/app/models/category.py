from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Ltree, TimestampMixin


class Category(TimestampMixin, Base):
    """Adjacency list (parent_id) + materialized path (ltree of ids, e.g. "1.4.9").

    parent_id keeps referential integrity; `path` makes subtree / ancestor
    queries a single indexed lookup at any depth.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1000))
    path: Mapped[str] = mapped_column(Ltree())
    sort_order: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))

    parent: Mapped[Optional["Category"]] = relationship(
        remote_side="Category.id", back_populates="children", lazy="raise"
    )
    children: Mapped[list["Category"]] = relationship(
        back_populates="parent", lazy="raise", passive_deletes="all"
    )

    __table_args__ = (Index("ix_categories_path_gist", "path", postgresql_using="gist"),)

    @property
    def depth(self) -> int:
        return self.path.count(".") + 1 if self.path else 0
