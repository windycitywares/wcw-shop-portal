"""How complete are the product listings? Complete listings rank better in search and convert better.

Each published product is checked against a short list of rules. A rule has a weight (how much it matters);
a product's score is the share of weight it satisfies, and the catalog score is the average (0-100).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

Row = Mapping[str, Any]

MIN_DESCRIPTION = 120
MIN_PHOTOS = 3


@dataclass(frozen=True)
class Check:
    key: str
    label: str  # plural noun phrase: "{n} {label}"
    weight: int
    failed: Callable[[Row], bool]
    fix: str  # what to do, as a short imperative


def _text(value: Any) -> str:
    return str(value).strip() if value else ""


CHECKS: tuple[Check, ...] = (
    Check("no_price", "listings with no price", 3, lambda r: not r.get("base_price"), "Set a price"),
    Check("no_photos", "listings without photos", 3, lambda r: (r.get("images") or 0) == 0, "Add product photos"),
    Check("few_photos", f"listings with fewer than {MIN_PHOTOS} photos", 1, lambda r: 0 < (r.get("images") or 0) < MIN_PHOTOS,
          f"Add photos (aim for {MIN_PHOTOS} or more, including a size reference)"),
    Check("short_description", f"listings with a description under {MIN_DESCRIPTION} characters", 2,
          lambda r: len(_text(r.get("description"))) < MIN_DESCRIPTION, "Describe size, capacity, material and finish"),
    Check("no_category", "listings without a category", 2, lambda r: r.get("category_id") is None, "Choose a category"),
    Check("no_tags", "listings without search tags", 1, lambda r: (r.get("tags") or 0) == 0, "Add tags shoppers would search for"),
    Check("no_seo", "listings without a search-engine description", 1, lambda r: not _text(r.get("seo_description")), "Write a short search-engine description"),
    Check("no_cost", "listings without a cost price", 1, lambda r: r.get("cost_price") is None, "Enter the cost price so profit reports are accurate"),
)
TOTAL_WEIGHT = sum(c.weight for c in CHECKS)


def product_score(row: Row) -> tuple[int, list[Check]]:
    """(score 0-100, the checks it failed)"""
    failed = [c for c in CHECKS if c.failed(row)]
    lost = sum(c.weight for c in failed)
    return round(100 * (TOTAL_WEIGHT - lost) / TOTAL_WEIGHT), failed


def assess(rows: list[Row], worst: int = 20) -> dict[str, Any]:
    """Catalog score, how many listings fail each rule, and the listings with the most to fix."""
    if not rows:
        return {"score": None, "products": 0, "issues": {}, "checks": [], "worst": []}
    scored = []
    counts = {c.key: 0 for c in CHECKS}
    for row in rows:
        score, failed = product_score(row)
        for c in failed:
            counts[c.key] += 1
        scored.append((score, row, failed))
    overall = round(sum(s for s, _, _ in scored) / len(scored))
    scored.sort(key=lambda t: (t[0], -(t[1].get("id") or 0)))
    return {
        "score": overall,
        "products": len(rows),
        "issues": {c.label: counts[c.key] for c in CHECKS if counts[c.key]},
        "checks": [{"key": c.key, "label": c.label, "count": counts[c.key], "weight": c.weight, "fix": c.fix} for c in CHECKS],
        "worst": [
            {"id": r.get("id"), "title": r.get("title"), "slug": r.get("slug"), "score": s, "problems": [c.fix for c in failed]}
            for s, r, failed in scored if failed
        ][:worst],
    }
