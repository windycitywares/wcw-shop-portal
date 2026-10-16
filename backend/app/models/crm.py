from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CrmOutbox(Base):
    """A change the CRM must hear about (migration 0014). Filled by app/core/crm_events.py, sent by
    app/services/crm_sync.py, which builds the payload from the current row at send time."""

    __tablename__ = "crm_outbox"
    __table_args__ = (
        Index("ix_crm_outbox_due", "status", "next_attempt_at"),
        Index("ix_crm_outbox_ref", "kind", "ref_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # order | customer | newsletter
    ref_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
