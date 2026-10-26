"""What a change is worth saying to staff at once, in words. Pure: no database, no SQLAlchemy.

app/core/live_events.py feeds it the before/after values of the fields that matter and writes what comes back
into `live_events`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

# Above this many changed products in one save (an import, a bulk edit) staff get one line, not one each.
PRODUCT_BURST = 3
STATUS_WORDS = {"processing": "is being prepared", "shipped": "shipped", "delivered": "delivered", "cancelled": "cancelled"}


@dataclass(frozen=True)
class Said:
    kind: str
    title: str
    detail: str | None = None


def money(value: Any) -> str:
    try:
        return f"${Decimal(str(value or 0)):,.2f}"
    except (ArithmeticError, ValueError):
        return ""


def _str(value: Any) -> str | None:
    return None if value is None else str(getattr(value, "value", value))


def order_change(number: str, name: str | None, total: Any, before: dict[str, Any], after: dict[str, Any], is_new: bool) -> Said | None:
    """One line per order per save, the most important first: placed, refunded, paid, then a status change.
    `before`/`after` hold placed_at, payment_status and status."""
    who = f"{name} · {money(total)}" if name else money(total)
    placed_now = after.get("placed_at") is not None and (is_new or before.get("placed_at") is None)
    if placed_now:
        return Said("order.new", f"New order #{number}", who)
    pay_before, pay_after = _str(before.get("payment_status")), _str(after.get("payment_status"))
    if pay_after != pay_before:
        if pay_after in ("refunded", "partially_refunded"):
            return Said("order.refund", f"Refund on order #{number}", who)
        if pay_after == "paid":
            return Said("order.paid", f"Order #{number} paid", who)
        if pay_after == "failed":
            return Said("order.status", f"Payment failed on order #{number}", who)
    st_before, st_after = _str(before.get("status")), _str(after.get("status"))
    if st_after != st_before and st_after in STATUS_WORDS:
        return Said("order.status", f"Order #{number} {STATUS_WORDS[st_after]}", who)
    return None


def products_changed(titles: list[tuple[str, bool]]) -> list[Said]:
    """`titles` = (title, is_new) of the products changed in one save."""
    if len(titles) > PRODUCT_BURST:
        return [Said("product.changed", f"{len(titles)} products updated")]
    return [Said("product.changed", f"Product {'added' if new else 'updated'}: {title}") for title, new in titles]
