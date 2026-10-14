"""Abandoned-cart report for staff."""

from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import Money


class CartLineOut(BaseModel):
    product_id: int
    title: str
    quantity: int


class CartRowOut(BaseModel):
    id: int
    status: str  # active | abandoned | converted | recovered
    items: list[CartLineOut]
    item_count: int
    subtotal: Money
    coupon_code: str | None
    email: str | None  # only when the shopper asked for reminders
    reminders_sent: int
    checkout_started: bool
    created_at: datetime
    last_activity_at: datetime
    order_number: str | None = None


class CartSummaryOut(BaseModel):
    started: int
    converted: int
    abandoned: int
    active: int
    abandoned_value: Money
    abandonment_rate: float | None
    reachable: int  # abandoned carts whose owner agreed to reminders
    reminders_sent: int
    recovered: int
    recovered_value: Money
    reached_checkout: int


class CartListOut(BaseModel):
    items: list[CartRowOut]
    total: int
    page: int
    page_size: int
    summary: CartSummaryOut
