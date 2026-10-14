"""What the storefront reports about a visit, once the visitor has accepted analytics."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.core.i18n import LANG_PATTERN

ID_PATTERN = r"^[A-Za-z0-9_-]{16,40}$"


class TrackEventIn(BaseModel):
    type: str = Field(max_length=24)
    path: str | None = Field(default=None, max_length=500)
    product_id: int | None = Field(default=None, ge=1, le=2**53)
    value: Decimal | None = Field(default=None, ge=0, le=1_000_000, max_digits=12, decimal_places=2)
    data: dict[str, Any] = Field(default_factory=dict)


class LandingIn(BaseModel):
    """How the visit began. Sent with every batch; only the first one is used."""

    path: str | None = Field(default=None, max_length=500)
    referrer: str | None = Field(default=None, max_length=500)
    utm_source: str | None = Field(default=None, max_length=100)
    utm_medium: str | None = Field(default=None, max_length=100)
    utm_campaign: str | None = Field(default=None, max_length=150)
    locale: str | None = Field(default=None, pattern=LANG_PATTERN)


class TrackIn(BaseModel):
    session_id: str = Field(pattern=ID_PATTERN)
    visitor_id: str = Field(pattern=ID_PATTERN)
    landing: LandingIn | None = None
    events: list[TrackEventIn] = Field(min_length=1, max_length=25)


class ConsentIn(BaseModel):
    accepted: bool
