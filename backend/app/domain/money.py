"""Money helpers. All amounts are `Decimal` with two places; never floats."""

from collections.abc import Sequence
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def q2(value: Decimal | int | float | str) -> Decimal:
    """Round half up to cents (the way shoppers expect: 2.675 -> 2.68)."""
    return Decimal(str(value) if isinstance(value, float) else value).quantize(CENT, rounding=ROUND_HALF_UP)


def to_cents(value: Decimal | int | str) -> int:
    return int((q2(value) * 100).to_integral_value())


def from_cents(cents: int) -> Decimal:
    return (Decimal(cents) / 100).quantize(CENT)


def percent_of(amount: Decimal, percent: Decimal) -> Decimal:
    return q2(amount * percent / 100)


def allocate(total: Decimal, weights: Sequence[Decimal]) -> list[Decimal]:
    """Split `total` in proportion to `weights` so the parts add up to exactly `total`.

    Largest-remainder method on whole cents: every part is rounded down, then the leftover cents
    go to the parts with the biggest fractional remainder (ties: earlier part first).
    """
    n = len(weights)
    if n == 0:
        return []
    cents = to_cents(total)
    weight_sum = sum(weights, Decimal(0))
    if cents == 0 or weight_sum <= 0:
        return [ZERO] * n
    exact = [Decimal(cents) * w / weight_sum for w in weights]
    parts = [int(x.to_integral_value(rounding=ROUND_FLOOR)) for x in exact]
    leftover = cents - sum(parts)
    order = sorted(range(n), key=lambda i: (exact[i] - parts[i], -i), reverse=True)
    for i in order[:leftover]:
        parts[i] += 1
    return [from_cents(p) for p in parts]
