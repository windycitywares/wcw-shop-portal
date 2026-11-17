"""Etsy → shop: see migrations/sql/0023_etsy.sql and docs/ETSY.md. Separate from the storefront's products and orders."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_NOW = func.now()


class EtsyConnection(Base):
    __tablename__ = "etsy_connection"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    client_id: Mapped[str | None] = mapped_column(String(100))  # the app's keystring
    client_secret_enc: Mapped[str | None] = mapped_column(Text)  # the shared secret, sealed
    etsy_shop_id: Mapped[int | None] = mapped_column(BigInteger)
    shop_name: Mapped[str | None] = mapped_column(String(200))
    access_token: Mapped[str | None] = mapped_column(Text)  # sealed
    refresh_token: Mapped[str | None] = mapped_column(Text)  # sealed
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str | None] = mapped_column(String(500))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_by_id: Mapped[int | None] = mapped_column(BigInteger)
    oauth_state: Mapped[str | None] = mapped_column(String(100))
    oauth_verifier: Mapped[str | None] = mapped_column(String(200))
    listings_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    orders_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW, onupdate=_NOW)


class EtsyListing(Base):
    __tablename__ = "etsy_listings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    etsy_listing_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20), default="active", index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    quantity: Mapped[int | None] = mapped_column(Integer)
    skus: Mapped[list] = mapped_column(JSONB, default=list)
    url: Mapped[str | None] = mapped_column(String(500))
    images: Mapped[list] = mapped_column(JSONB, default=list)
    variations: Mapped[list] = mapped_column(JSONB, default=list)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    etsy_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    internal_supplier: Mapped[str | None] = mapped_column(String(200))
    internal_purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    internal_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW, onupdate=_NOW)


class EtsyOrder(Base):
    __tablename__ = "etsy_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    etsy_receipt_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    etsy_state: Mapped[str | None] = mapped_column(String(30))
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ship_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    buyer_name: Mapped[str | None] = mapped_column(String(200))
    etsy_buyer_id: Mapped[int | None] = mapped_column(BigInteger)
    buyer_email: Mapped[str | None] = mapped_column(String(320))
    buyer_phone: Mapped[str | None] = mapped_column(String(50))
    ship_address: Mapped[dict] = mapped_column(JSONB, default=dict)
    gift_message: Mapped[str | None] = mapped_column(Text)
    buyer_note: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    items_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    shipping_charged: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discounts: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    etsy_fees: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    etsy_fees_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    costs_prefilled: Mapped[bool] = mapped_column(Boolean, default=False)
    supplier: Mapped[str | None] = mapped_column(String(200))
    supplier_order_number: Mapped[str | None] = mapped_column(String(100))
    shipping_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    carrier: Mapped[str | None] = mapped_column(String(60))
    tracking_number: Mapped[str | None] = mapped_column(String(100))
    tracking_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tracking_error: Mapped[str | None] = mapped_column(String(300))
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    etsy_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW, onupdate=_NOW)


class EtsyOrderItem(Base):
    __tablename__ = "etsy_order_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("etsy_orders.id", ondelete="CASCADE"), index=True)
    etsy_transaction_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    etsy_listing_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(300))
    sku: Mapped[str | None] = mapped_column(String(100))
    variations: Mapped[list] = mapped_column(JSONB, default=list)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)


class EtsyOrderEvent(Base):
    __tablename__ = "etsy_order_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("etsy_orders.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(500))
    source: Mapped[str] = mapped_column(String(10), default="team")
    actor_id: Mapped[int | None] = mapped_column(BigInteger)
    actor_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
