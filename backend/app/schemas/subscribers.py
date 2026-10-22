from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.i18n import LANG_PATTERN
from app.schemas.common import Page


class SubscriberOut(BaseModel):
    id: int
    email: str
    locale: str | None
    source: str
    subscribed: bool
    subscribed_at: datetime
    unsubscribed_at: datetime | None
    paused: bool = False
    paused_at: datetime | None = None
    welcome_coupon: str | None
    has_ordered: bool


class SubscriberCounts(BaseModel):
    all: int
    subscribed: int
    paused: int = 0
    unsubscribed: int


class SubscriberList(Page[SubscriberOut]):
    counts: SubscriberCounts


class SubscriberAdd(BaseModel):
    email: EmailStr
    locale: str = Field(default="en", pattern=LANG_PATTERN)
