"""Order status rules, kept apart from the database so they are easy to read and test."""

from decimal import Decimal

from app.domain.money import q2

PENDING, PAID, PROCESSING, SHIPPED, DELIVERED, CANCELLED, REFUNDED = (
    "pending", "paid", "processing", "shipped", "delivered", "cancelled", "refunded",
)

# From each status, the statuses staff can move an order to by hand.
TRANSITIONS: dict[str, frozenset[str]] = {
    PENDING: frozenset({PAID, CANCELLED}),
    PAID: frozenset({PROCESSING, SHIPPED, CANCELLED, REFUNDED}),
    PROCESSING: frozenset({SHIPPED, CANCELLED, REFUNDED}),
    SHIPPED: frozenset({DELIVERED, REFUNDED}),
    DELIVERED: frozenset({REFUNDED}),
    CANCELLED: frozenset(),
    REFUNDED: frozenset(),
}

# Orders that count as sales in reports (money received and not fully given back).
SOLD_STATUSES = (PAID, PROCESSING, SHIPPED, DELIVERED)
# Orders that still hold stock and (possibly) a coupon use.
OPEN_STATUSES = (PENDING, PAID, PROCESSING, SHIPPED, DELIVERED)


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, frozenset())


def payment_status_after_refund(grand_total: Decimal, refunded_total: Decimal) -> str:
    """'refunded' once everything is given back, 'partially_refunded' while some is, else 'paid'."""
    refunded = q2(refunded_total)
    if refunded <= 0:
        return "paid"
    return "refunded" if refunded >= q2(grand_total) else "partially_refunded"


def refundable(grand_total: Decimal, refunded_total: Decimal) -> Decimal:
    return max(Decimal("0.00"), q2(grand_total) - q2(refunded_total))
