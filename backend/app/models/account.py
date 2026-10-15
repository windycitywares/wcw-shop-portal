from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PasswordResetToken(Base):
    """One-time password-reset link. Only a SHA-256 hash of the token is stored."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class Address(TimestampMixin, Base):
    """A saved shipping address. Each customer can keep several; one is the default."""

    __tablename__ = "addresses"
    __table_args__ = (  # at most one default address per customer
        Index("uq_addresses_one_default", "user_id", unique=True, postgresql_where=text("is_default")),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str | None] = mapped_column(String(50))  # "Home", "Mom's house", ...
    full_name: Mapped[str] = mapped_column(String(200))
    company: Mapped[str | None] = mapped_column(String(200))
    line1: Mapped[str] = mapped_column(String(200))
    line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))  # state / province
    postal_code: Mapped[str] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(2), default="US", server_default="US")  # ISO 3166-1 alpha-2
    phone: Mapped[str | None] = mapped_column(String(40))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class ContactMessage(TimestampMixin, Base):
    """Messages sent from the Contact page (kept even if the email notification fails)."""

    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    order_number: Mapped[str | None] = mapped_column(String(32))
    locale: Mapped[str | None] = mapped_column(String(5))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    emailed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # inbox (0009): new -> open -> replied/closed; spam is kept out of the default view
    status: Mapped[str] = mapped_column(String(16), default="new", server_default="new")
    staff_note: Mapped[str | None] = mapped_column(Text)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handled_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        CheckConstraint("status IN ('new', 'open', 'replied', 'closed', 'spam')", name="ck_contact_messages_status"),
        Index("ix_contact_messages_status_created", "status", text("created_at DESC")),
        Index("ix_contact_messages_email", text("lower(email)")),
    )


class ContactReply(Base):
    """An answer to a contact message, written in the admin and emailed to the sender."""

    __tablename__ = "contact_replies"
    __table_args__ = (Index("ix_contact_replies_message", "message_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contact_messages.id", ondelete="CASCADE"))
    author_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    author_email: Mapped[str | None] = mapped_column(String(320))
    body: Mapped[str] = mapped_column(Text)
    emailed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
