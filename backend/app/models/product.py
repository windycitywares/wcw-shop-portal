from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ContentStatus, StockStatus
from app.models.base import Base, TimestampMixin, pg_enum
from app.models.category import Category


class Product(TimestampMixin, Base):
    """A sellable item. Variants are child rows (parent_id) with their own SKU/price.

    `attributes` (JSONB) holds per-product data such as {"Material": "Oak",
    "Color": ["Red", "Blue"]} without schema changes; it is GIN-indexed for
    faceted filtering.
    """

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    sku: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    base_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    stock_status: Mapped[StockStatus] = mapped_column(
        pg_enum(StockStatus, "stock_status"),
        default=StockStatus.IN_STOCK,
        server_default=StockStatus.IN_STOCK.value,
    )
    stock_quantity: Mapped[int | None]
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    images: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'::text[]")
    )
    status: Mapped[ContentStatus] = mapped_column(
        pg_enum(ContentStatus, "content_status"),
        default=ContentStatus.DRAFT,
        server_default=ContentStatus.DRAFT.value,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(30), default="manual", server_default="manual")
    source_ref: Mapped[str | None] = mapped_column(String(255))
    seo_title: Mapped[str | None] = mapped_column(String(300))
    seo_description: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    parent: Mapped[Optional["Product"]] = relationship(
        remote_side="Product.id", back_populates="variants", lazy="raise"
    )
    variants: Mapped[list["Product"]] = relationship(
        back_populates="parent", lazy="raise", passive_deletes=True, order_by="Product.id"
    )
    category: Mapped[Optional[Category]] = relationship(lazy="raise")

    __table_args__ = (
        CheckConstraint("base_price >= 0", name="price_nonneg"),
        Index(
            "uq_products_source_ref",
            "source",
            "source_ref",
            unique=True,
            postgresql_where=text("source_ref IS NOT NULL"),
        ),
        Index(
            "ix_products_attributes",
            "attributes",
            postgresql_using="gin",
            postgresql_ops={"attributes": "jsonb_path_ops"},
        ),
    )
