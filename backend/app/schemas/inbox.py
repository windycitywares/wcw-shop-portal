"""Contact inbox (admin): messages from the Contact page, their status, notes and replies."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import Money, ORMModel

InboxStatus = Literal["new", "open", "replied", "closed", "spam"]


class InboxItemOut(ORMModel):
    id: int
    name: str
    email: str
    subject: str
    preview: str
    order_number: str | None
    status: InboxStatus
    replies: int
    created_at: datetime


class InboxListOut(BaseModel):
    items: list[InboxItemOut]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]


class ReplyOut(ORMModel):
    id: int
    author_email: str | None
    body: str
    emailed: bool
    created_at: datetime


class EarlierMessage(BaseModel):
    id: int
    subject: str
    status: InboxStatus
    created_at: datetime


class CustomerOrder(BaseModel):
    id: int
    number: str
    status: str
    grand_total: Money
    placed_at: datetime | None


class InboxMessageOut(ORMModel):
    id: int
    name: str
    email: str
    subject: str
    message: str
    order_number: str | None
    order_id: int | None = None
    locale: str | None
    status: InboxStatus
    staff_note: str | None
    emailed: bool
    signed_in: bool
    handled_at: datetime | None
    handled_by_email: str | None = None
    created_at: datetime
    replies: list[ReplyOut]
    earlier: list[EarlierMessage]
    orders: list[CustomerOrder]


class InboxUpdateIn(BaseModel):
    status: InboxStatus | None = None
    staff_note: str | None = Field(None, max_length=5000)


class InboxReplyIn(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)
    close: bool = False  # mark the conversation closed instead of "replied"

    @field_validator("body")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Write a reply first")
        return v


class InboxReplyOut(BaseModel):
    message: InboxMessageOut
    emailed: bool
