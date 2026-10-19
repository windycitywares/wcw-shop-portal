"""A Contact: anyone the shop has a relationship with (customer, account holder, newsletter subscriber,
contact-form sender, stock-alert requester). A superset of `User` and of the customers the CRM reads today."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (
        Index("ix_contacts_email", "email"),
        Index("ix_contacts_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    # Where we met them: signup, order, newsletter, contact_form, stock_alert, import.
    source: Mapped[str] = mapped_column(String(32), server_default="import", nullable=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"))
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
