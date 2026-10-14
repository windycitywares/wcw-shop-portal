"""Store settings, shipping, tax, sales, coupons and the order paper trail."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_TRUE = text("true")
_FALSE = text("false")
_ZERO = text("0")
_EMPTY_LIST = text("'[]'::jsonb")


class Setting(Base):
    """One store setting (key -> JSON value). Defaults live in code; only changed keys are stored."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))


class ShippingMethod(TimestampMixin, Base):
    __tablename__ = "shipping_methods"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(300))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    free_over: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))  # free when the goods come to this much
    min_days: Mapped[int | None] = mapped_column(Integer)
    max_days: Mapped[int | None] = mapped_column(Integer)
    countries: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=_EMPTY_LIST)  # [] = everywhere
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=_TRUE)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=_ZERO)

    __table_args__ = (CheckConstraint("price >= 0", name="price_nonneg"),)


class TaxRate(TimestampMixin, Base):
    __tablename__ = "tax_rates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(2))
    region: Mapped[str | None] = mapped_column(String(100))  # state / province; empty = whole country
    rate: Mapped[Decimal] = mapped_column(Numeric(6, 3))  # percent
    applies_to_shipping: Mapped[bool] = mapped_column(Boolean, default=False, server_default=_FALSE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=_TRUE)

    __table_args__ = (CheckConstraint("rate >= 0 AND rate <= 100", name="rate_range"),)


class Sale(TimestampMixin, Base):
    """An automatic price cut on products, shown on the storefront while it is live."""

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    label: Mapped[str | None] = mapped_column(String(40))  # short badge text, e.g. "Autumn sale"
    kind: Mapped[str] = mapped_column(String(10))  # percent | fixed
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    scope: Mapped[str] = mapped_column(String(10), default="all", server_default="all")  # all | category | products
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id", ondelete="SET NULL"))
    product_ids: Mapped[list[int]] = mapped_column(JSONB, default=list, server_default=_EMPTY_LIST)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=_TRUE)
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        CheckConstraint("kind IN ('percent', 'fixed')", name="kind_valid"),
        CheckConstraint("scope IN ('all', 'category', 'products')", name="scope_valid"),
        CheckConstraint("value > 0", name="value_positive"),
        Index("ix_sales_active_window", "is_active", "starts_at", "ends_at"),
    )


class Coupon(TimestampMixin, Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)  # stored upper case
    description: Mapped[str | None] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(14))  # percent | fixed | free_shipping
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    min_subtotal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    max_discount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    scope: Mapped[str] = mapped_column(String(10), default="all", server_default="all")
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id", ondelete="SET NULL"))
    product_ids: Mapped[list[int]] = mapped_column(JSONB, default=list, server_default=_EMPTY_LIST)
    exclude_sale_items: Mapped[bool] = mapped_column(Boolean, default=False, server_default=_FALSE)
    first_order_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default=_FALSE)
    usage_limit: Mapped[int | None] = mapped_column(Integer)
    per_customer_limit: Mapped[int | None] = mapped_column(Integer)
    used_count: Mapped[int] = mapped_column(Integer, default=0, server_default=_ZERO)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=_TRUE)
    # Personal coupons only work for this account or email address.
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[str | None] = mapped_column(String(320))
    # Who the code was sent to (welcome and personal codes); informational, not enforced.
    issued_to: Mapped[str | None] = mapped_column(String(320), index=True)
    campaign: Mapped[str | None] = mapped_column(String(80), index=True)  # batch name for generated codes
    source: Mapped[str] = mapped_column(String(12), default="manual", server_default="manual")
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        CheckConstraint("kind IN ('percent', 'fixed', 'free_shipping')", name="kind_valid"),
        CheckConstraint("scope IN ('all', 'category', 'products')", name="scope_valid"),
        CheckConstraint("source IN ('manual', 'generated', 'welcome', 'personal')", name="source_valid"),
        CheckConstraint("value >= 0", name="value_nonneg"),
    )


class CouponRedemption(Base):
    """One row per order that used a coupon (kept for reports even if the coupon is edited)."""

    __tablename__ = "coupon_redemptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    coupon_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("coupons.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[str] = mapped_column(String(320), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OrderEvent(Base):
    """The order's timeline: placed, paid, shipped, refunded, notes."""

    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(500))
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reason: Mapped[str | None] = mapped_column(String(300))
    restocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=_FALSE)
    provider_ref: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)


__all__ = [
    "Coupon", "CouponRedemption", "OrderEvent", "Refund", "Sale", "Setting", "ShippingMethod", "TaxRate",
]
