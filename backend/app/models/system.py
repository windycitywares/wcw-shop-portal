from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppMode(Base):
    """Live / Test switch (one row). Read as public.app_mode by app/core/appmode.py; changed by services/testenv.py."""

    __tablename__ = "app_mode"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_app_mode_single"),
        CheckConstraint("mode IN ('live', 'test')", name="ck_app_mode_mode"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, server_default=text("1"))
    mode: Mapped[str] = mapped_column(String(8), server_default="live")
    test_mail_to: Mapped[str | None] = mapped_column(String(320))
    test_login_emails: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), default=list)
    test_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    changed_by_email: Mapped[str | None] = mapped_column(String(320))
