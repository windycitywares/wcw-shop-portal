from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, text
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
    notes: Mapped[str | None] = mapped_column(Text)  # the customer's note at checkout
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Public access: the unguessable token in the "view your order" link from the confirmation email.
    access_token: Mapped[str] = mapped_column(String(64), unique=True)
    customer_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    locale: Mapped[str | None] = mapped_column(String(5))
    # unpaid | paid | partially_refunded | refunded | failed (a string, so no enum migration is needed)
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid", server_default="unpaid")
    refunded_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    coupon_code: Mapped[str | None] = mapped_column(String(40))
    # [{"type": "coupon"|"rule"|"free_shipping", "label": ..., "code": ..., "amount": 12.5}]
    discounts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=0, server_default=_ZERO)
    carrier: Mapped[str | None] = mapped_column(String(60))
    tracking_url: Mapped[str | None] = mapped_column(String(500))
    # Analytics attribution (only set when the visitor accepted analytics)
    session_id: Mapped[str | None] = mapped_column(String(40))
    channel: Mapped[str | None] = mapped_column(String(30))
    device: Mapped[str | None] = mapped_column(String(10))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
    slug: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String(1000))
    list_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # before any sale
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # purchase cost, for margin
    sale_id: Mapped[int | None] = mapped_column(BigInteger)  # the sale that set unit_price (no FK on purpose)
    discount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)  # share of order-level discounts
    refunded_quantity: Mapped[int] = mapped_column(default=0, server_default=_ZERO)

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)
