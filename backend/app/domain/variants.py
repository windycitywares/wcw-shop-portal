"""New variants follow the existing numbering: parent SKU + "-<n>" (ETSY-4519546536-1, -2, …)."""

from __future__ import annotations

import re
from collections.abc import Iterable


def next_variant_sku(parent_sku: str, existing: Iterable[str]) -> str:
    """One past the highest number already used after the parent's SKU (case-insensitive); free of every SKU given."""
    taken = {s.upper() for s in existing}
    pattern = re.compile(rf"^{re.escape(parent_sku.upper())}-(\d+)$")
    numbers = [int(m.group(1)) for s in taken if (m := pattern.match(s))]
    n = max(numbers, default=0) + 1
    while f"{parent_sku}-{n}".upper() in taken:
        n += 1
    return f"{parent_sku}-{n}"
