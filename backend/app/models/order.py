from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import FulfillmentStatus, OrderStatus
from app.models.base import Base, TimestampMixin, pg_enum

_ZERO = text("0")


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    email: Mapped[str] = mapped_column(String(320))
    status: Mapped[OrderStatus] = mapped_column(
        pg_enum(OrderStatus, "order_status"),
        default=OrderStatus.PENDING,
        server_default=OrderStatus.PENDING.value,
    )
    fulfillment_status: Mapped[FulfillmentStatus] = mapped_column(
        pg_enum(FulfillmentStatus, "fulfillment_status"),
        default=FulfillmentStatus.UNFULFILLED,
        server_default=FulfillmentStatus.UNFULFILLED.value,
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    shipping_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    shipping_address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    billing_address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    shipping_method: Mapped[str | None] = mapped_column(String(100))
    tracking_number: Mapped[str | None] = mapped_column(String(100))
    payment_provider: Mapped[str | None] = mapped_column(String(30))
    payment_intent_id: Mapped[str | None] = mapped_column(String(255), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("products.id", ondelete="SET NULL")
    )
    # Snapshot of the product at purchase time
    sku: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int]
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)
