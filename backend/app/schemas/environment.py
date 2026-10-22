"""Live / Test switch (admin)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class EnvironmentOut(BaseModel):
    mode: Literal["live", "test"]
    effective: Literal["live", "test"]
    test_exists: bool
    test_synced_at: datetime | None
    test_mail_to: str | None
    test_login_emails: list[str] = []
    test_size_bytes: int | None
    out_of_date: bool
    changed_at: datetime | None
    changed_by_email: str | None
    stripe_test_configured: bool
    stats: dict[str, float | int] | None = None


class ModeIn(BaseModel):
    mode: Literal["live", "test"]


class MailToIn(BaseModel):
    email: EmailStr | None = None


class LoginsIn(BaseModel):
    """Shopper addresses allowed to sign in on the test copy (staff always may)."""

    emails: list[EmailStr] = Field(default_factory=list, max_length=200)
