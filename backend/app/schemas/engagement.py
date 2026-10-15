"""Reviews, wishlist and back-in-stock requests."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.i18n import LANG_PATTERN
from app.schemas.common import Money, ORMModel


def _one_line(v: str | None) -> str | None:
    if v is None:
        return None
    return " ".join(v.split()) or None


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=160)
    body: str = Field(min_length=10, max_length=4000)
    locale: str = Field(default="en", pattern=LANG_PATTERN)

    @field_validator("title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        return _one_line(v)

    @field_validator("body")
    @classmethod
    def _body(cls, v: str) -> str:
        return "\n".join(line.rstrip() for line in v.strip().splitlines())


class ReviewOut(ORMModel):
    id: int
    author_name: str
    rating: int
    title: str | None
    body: str
    verified: bool
    helpful_count: int
    created_at: datetime
    reply: str | None
    replied_at: datetime | None
    helpful_by_me: bool = False


class ReviewSummary(BaseModel):
    average: Money
    count: int
    distribution: dict[int, int]  # stars -> number of reviews


class ReviewsOut(BaseModel):
    summary: ReviewSummary
    items: list[ReviewOut]
    total: int
    page: int
    page_size: int
    can_review: bool = False  # signed in and has not reviewed yet
    purchased: bool = False  # the signed-in shopper bought it (reviews will be marked verified)


class ReviewSubmittedOut(BaseModel):
    status: Literal["pending", "approved"]
    review: ReviewOut


class ReviewAdminOut(ORMModel):
    id: int
    product_id: int
    product_title: str = ""
    product_slug: str = ""
    author_name: str
    rating: int
    title: str | None
    body: str
    status: str
    verified: bool
    helpful_count: int
    reply: str | None
    created_at: datetime


class ReviewAdminListOut(BaseModel):
    items: list[ReviewAdminOut]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]  # status -> number


class ReviewModerateIn(BaseModel):
    status: Literal["approved", "rejected", "pending"]
    reply: str | None = Field(default=None, max_length=2000)

    @field_validator("reply")
    @classmethod
    def _reply(cls, v: str | None) -> str | None:
        return v.strip() or None if v else None


class StockAlertIn(BaseModel):
    """Old "notify me" form (email field ignored now: requests use the signed-in account)."""

    email: EmailStr | None = None
    locale: str = Field(default="en", pattern=LANG_PATTERN)


class StockRequestIn(BaseModel):
    options: dict[str, str] = Field(default_factory=dict, max_length=10)
    note: str | None = Field(default=None, max_length=1000)
    locale: str = Field(default="en", pattern=LANG_PATTERN)


class StockRequestCreated(BaseModel):
    kind: Literal["restock", "request"]
    options: dict[str, str]
    already: bool


class MyStockRequest(BaseModel):
    id: int
    product_id: int
    title: str
    slug: str
    image: str | None
    options: dict[str, str]
    note: str | None
    kind: Literal["restock", "request"]
    status: Literal["waiting", "notified", "closed"]
    created_at: datetime
    notified_at: datetime | None


class AdminStockRequest(MyStockRequest):
    sku: str | None
    variant: str | None
    in_stock: bool
    email: str
    closed_at: datetime | None
    handled_by_email: str | None


class AdminStockRequestList(BaseModel):
    items: list[AdminStockRequest]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]


class StockRequestNotifyIn(BaseModel):
    message: str | None = Field(default=None, max_length=1000)
