"""First-party analytics (consent-based; no IP addresses are stored)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

_NOW = text("now()")


class AnalyticsSession(Base):
    __tablename__ = "analytics_sessions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    visitor_id: Mapped[str] = mapped_column(String(40))
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    landing_path: Mapped[str | None] = mapped_column(String(500))
    referrer_host: Mapped[str | None] = mapped_column(String(255))
    channel: Mapped[str] = mapped_column(String(30), default="direct", server_default="direct")
    utm_source: Mapped[str | None] = mapped_column(String(100))
    utm_medium: Mapped[str | None] = mapped_column(String(100))
    utm_campaign: Mapped[str | None] = mapped_column(String(150))
    device: Mapped[str | None] = mapped_column(String(10))
    browser: Mapped[str | None] = mapped_column(String(30))
    os: Mapped[str | None] = mapped_column(String(30))
    locale: Mapped[str | None] = mapped_column(String(5))
    is_new_visitor: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    page_views: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    event_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(40), ForeignKey("analytics_sessions.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(24))
    path: Mapped[str | None] = mapped_column(String(500))
    product_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("products.id", ondelete="SET NULL"))
    value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class ConsentDaily(Base):
    __tablename__ = "consent_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    accepted: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    declined: Mapped[int] = mapped_column(default=0, server_default=text("0"))
