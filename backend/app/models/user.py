from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import UserRole
from app.models.base import Base, TimestampMixin, pg_enum


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)  # stored lowercase
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(
        pg_enum(UserRole, "user_role"),
        default=UserRole.CUSTOMER,
        server_default=UserRole.CUSTOMER.value,
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    # Tokens issued before this moment are rejected (set when the password changes).
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notifications_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # admin bell: read up to here
    # How live updates reach this person (0022): only what they changed; app/domain/live_prefs.py adds the defaults.
    notification_prefs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class NewsletterSubscriber(TimestampMixin, Base):
    """Marketing consent registry: everyone who opted in to emails, and who later unsubscribed."""

    __tablename__ = "newsletter_subscribers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    locale: Mapped[str | None] = mapped_column(String(5))
    source: Mapped[str] = mapped_column(String(20), default="site", server_default="site")  # site | checkout | account
    unsubscribe_token: Mapped[str] = mapped_column(
        String(40), unique=True, server_default=text("md5(random()::text || clock_timestamp()::text)")
    )
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Paused by staff: still subscribed, but campaigns skip them until resumed. Service email is unaffected.
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    welcome_coupon: Mapped[str | None] = mapped_column(String(40))
