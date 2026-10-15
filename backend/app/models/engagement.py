"""Reviews, wishlists, back-in-stock alerts and email campaigns."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_NOW = text("now()")


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    order_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("orders.id", ondelete="SET NULL"))
    author_name: Mapped[str] = mapped_column(String(120))
    rating: Mapped[int] = mapped_column(SmallInteger)
    title: Mapped[str | None] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    locale: Mapped[str | None] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")  # pending | approved | rejected
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    helpful_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    reply: Mapped[str | None] = mapped_column(Text)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="rating"),)


class ReviewVote(Base):
    __tablename__ = "review_votes"

    review_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class WishlistItem(Base):
    __tablename__ = "wishlist_items"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class StockAlert(Base):
    """"Email me when it's back" request."""

    __tablename__ = "stock_alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    product_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    locale: Mapped[str | None] = mapped_column(String(5))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    # 0012: the option combination asked for ({"Size": "Large"}), a note from the customer, and the kind:
    # "restock" = a combination the shop sells, emailed automatically when back; "request" = one it doesn't sell, for staff.
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    note: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(10), default="restock", server_default="restock")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handled_by_email: Mapped[str | None] = mapped_column(String(320))


class Campaign(TimestampMixin, Base):
    """An email to a customer segment, optionally with a personal single-use coupon per recipient."""

    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    translations: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    segment: Mapped[str] = mapped_column(String(20), default="subscribers", server_default="subscribers")
    coupon_kind: Mapped[str | None] = mapped_column(String(14))
    coupon_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    coupon_expires_days: Mapped[int | None]
    coupon_min_subtotal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(10), default="draft", server_default="draft")
    recipients: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
