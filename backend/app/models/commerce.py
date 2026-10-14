"""Settings, promotions, carts, payments, order timeline, email outbox and audit log."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_ZERO = text("0")
_EMPTY_IDS = text("'{}'::bigint[]")
_EMPTY_JSON = text("'{}'::jsonb")
_EMPTY_LIST = text("'[]'::jsonb")
_NOW = text("now()")


class StoreSetting(Base):
    """One JSON document per settings group ("shipping", "tax", "welcome", ...)."""

    __tablename__ = "store_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=_EMPTY_JSON)
    updated_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class Sale(TimestampMixin, Base):
    """A time-boxed price reduction on all products, some categories or chosen products."""

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    badge: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(10), default="percent", server_default="percent")  # percent | fixed
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    scope: Mapped[str] = mapped_column(String(10), default="all", server_default="all")  # all | category | products
    category_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list, server_default=_EMPTY_IDS)
    product_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list, server_default=_EMPTY_IDS)
    exclude_product_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list, server_default=_EMPTY_IDS)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    translations: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=_EMPTY_JSON)
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        CheckConstraint("kind IN ('percent', 'fixed')", name="kind"),
        CheckConstraint("scope IN ('all', 'category', 'products')", name="scope"),
        CheckConstraint("value > 0", name="value_positive"),
    )


class Coupon(TimestampMixin, Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)  # stored upper-case
    name: Mapped[str | None] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(14), default="percent", server_default="percent")  # percent | fixed | free_shipping
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    max_discount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    min_subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    scope: Mapped[str] = mapped_column(String(10), default="order", server_default="order")  # order | category | products
    category_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list, server_default=_EMPTY_IDS)
    product_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list, server_default=_EMPTY_IDS)
    exclude_sale_items: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_limit: Mapped[int | None]
    per_customer_limit: Mapped[int | None]
    first_order_only: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    assigned_email: Mapped[str | None] = mapped_column(String(320))
    campaign: Mapped[str | None] = mapped_column(String(80))
    # manual | bulk | welcome | abandoned_cart | campaign | winback
    source: Mapped[str] = mapped_column(String(16), default="manual", server_default="manual")
    stackable: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    used_count: Mapped[int] = mapped_column(default=0, server_default=_ZERO)
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    coupon_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("coupons.id", ondelete="CASCADE"))
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[str] = mapped_column(String(320))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)

    __table_args__ = (Index("uq_coupon_redemptions_order", "coupon_id", "order_id", unique=True),)


class CartRule(TimestampMixin, Base):
    """Automatic discount applied at checkout without a code."""

    __tablename__ = "cart_rules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    # spend_percent | spend_fixed | qty_percent | qty_fixed | free_shipping
    kind: Mapped[str] = mapped_column(String(20))
    threshold_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    threshold_qty: Mapped[int | None]
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    max_discount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    scope: Mapped[str] = mapped_column(String(10), default="order", server_default="order")
    category_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list, server_default=_EMPTY_IDS)
    product_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list, server_default=_EMPTY_IDS)
    exclude_sale_items: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    priority: Mapped[int] = mapped_column(default=0, server_default=_ZERO)
    translations: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=_EMPTY_JSON)
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))


class Cart(TimestampMixin, Base):
    """Server-side snapshot of a shopper's cart (abandoned-cart reminders and reports)."""

    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    token: Mapped[str] = mapped_column(String(40), unique=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[str | None] = mapped_column(String(320))
    locale: Mapped[str | None] = mapped_column(String(5))
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, server_default=_EMPTY_LIST)
    item_count: Mapped[int] = mapped_column(default=0, server_default=_ZERO)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default=_ZERO)
    coupon_code: Mapped[str | None] = mapped_column(String(40))
    session_id: Mapped[str | None] = mapped_column(String(40))
    reminders_ok: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    checkout_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="SET NULL"))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_count: Mapped[int] = mapped_column(default=0, server_default=_ZERO)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recovery_coupon: Mapped[str | None] = mapped_column(String(40))


class Payment(TimestampMixin, Base):
    """A charge or a refund against an order, as reported by the payment provider."""

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))  # manual | stripe | test
    kind: Mapped[str] = mapped_column(String(10), default="charge", server_default="charge")  # charge | refund
    status: Mapped[str] = mapped_column(String(12), default="pending", server_default="pending")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    provider_ref: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=_EMPTY_JSON)
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))


class OrderEvent(Base):
    """Timeline entry on an order: status changes, notes, emails, refunds."""

    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(30))
    message: Mapped[str | None] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=_EMPTY_JSON)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    actor: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class EmailOutbox(TimestampMixin, Base):
    __tablename__ = "email_outbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    to_email: Mapped[str] = mapped_column(String(320))
    kind: Mapped[str] = mapped_column(String(30))
    subject: Mapped[str] = mapped_column(String(300))
    body_text: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str | None] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(10), default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(default=0, server_default=_ZERO)
    last_error: Mapped[str | None] = mapped_column(Text)
    related_type: Mapped[str | None] = mapped_column(String(20))
    related_id: Mapped[int | None] = mapped_column(BigInteger)
    send_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    actor_email: Mapped[str | None] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str | None] = mapped_column(String(30))
    entity_id: Mapped[str | None] = mapped_column(String(40))
    summary: Mapped[str | None] = mapped_column(String(500))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=_EMPTY_JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
