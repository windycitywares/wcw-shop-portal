"""Email campaigns: one message to a group of subscribers, optionally with a personal coupon for each."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.i18n import LANGUAGES
from app.schemas.common import Money, ORMModel

Segment = Literal["subscribers", "prospects", "customers", "new", "active", "loyal", "vip", "needs_nudge", "at_risk", "lapsed"]

SEGMENT_LABELS = {
    "subscribers": "Everyone who subscribed",
    "prospects": "Subscribers who haven't bought yet",
    "customers": "Subscribers who have bought",
    "new": "New customers",
    "active": "Active customers",
    "loyal": "Loyal customers",
    "vip": "VIP customers",
    "needs_nudge": "One-time buyers (60 to 180 days ago)",
    "at_risk": "Repeat customers going quiet",
    "lapsed": "Lapsed customers (over a year)",
}


def _one_line(v: str) -> str:
    return " ".join(v.split())


class CampaignText(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)

    @field_validator("subject")
    @classmethod
    def _subject(cls, v: str) -> str:
        return _one_line(v)

    @field_validator("body")
    @classmethod
    def _body(cls, v: str) -> str:
        return "\n".join(line.rstrip() for line in v.strip().splitlines())


class CampaignIn(CampaignText):
    name: str = Field(min_length=1, max_length=120)
    translations: dict[str, CampaignText] = Field(default_factory=dict)
    segment: Segment = "subscribers"
    coupon_kind: Literal["percent", "fixed", "free_shipping"] | None = None
    coupon_value: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    coupon_expires_days: int | None = Field(default=None, ge=1, le=365)
    coupon_min_subtotal: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)

    @field_validator("translations")
    @classmethod
    def _langs(cls, v: dict[str, CampaignText]) -> dict[str, CampaignText]:
        return {k: t for k, t in v.items() if k in LANGUAGES and k != "en"}

    @model_validator(mode="after")
    def _coupon(self) -> Self:
        if self.coupon_kind is None:
            self.coupon_value = self.coupon_expires_days = self.coupon_min_subtotal = None
            return self
        if self.coupon_kind == "free_shipping":
            self.coupon_value = Decimal("0")
        elif self.coupon_value is None:
            raise ValueError("Set the discount amount for the coupon")
        elif self.coupon_kind == "percent" and self.coupon_value > 100:
            raise ValueError("A percentage coupon can't be more than 100%")
        if self.coupon_expires_days is None:
            self.coupon_expires_days = 14
        return self


class CampaignOut(ORMModel):
    id: int
    name: str
    subject: str
    body: str
    translations: dict[str, CampaignText]
    segment: str
    coupon_kind: str | None
    coupon_value: Money | None
    coupon_expires_days: int | None
    coupon_min_subtotal: Money | None
    status: str  # draft | sent
    recipients: int
    sent_at: datetime | None
    created_at: datetime
    coupons_issued: int = 0
    coupons_redeemed: int = 0
    revenue: Money = Decimal("0")


class AudienceOut(BaseModel):
    segment: str
    label: str
    count: int


class SegmentChoice(BaseModel):
    key: str
    label: str


class CampaignListOut(BaseModel):
    items: list[CampaignOut]
    segments: list[SegmentChoice]
