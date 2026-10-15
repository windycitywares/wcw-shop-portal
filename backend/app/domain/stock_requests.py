"""Stock requests, the pure part: which option combinations a product has, which variant a combination is, and
whether the shopper is asking for something the shop sells ("restock") or something it doesn't ("request").

Products offer choices in two ways (see the storefront's PurchasePanel):
- variants: child products, each with attributes such as {"Size": "Large", "Wood": "Walnut"};
- list attributes on the product itself, such as {"Size": ["Small", "Large"]}, with one shared stock.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

MAX_NOTE = 1000


def values_of(value: Any) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]


def option_groups(attributes: Mapping[str, Any], variant_attributes: Iterable[Mapping[str, Any]]) -> dict[str, list[str]]:
    """{"Size": ["Small", "Large"], ...}: from the variants when there are any, else from the product's list attributes."""
    groups: dict[str, list[str]] = {}
    variants = list(variant_attributes)
    if variants:
        for attrs in variants:
            for key, value in attrs.items():
                for v in values_of(value):
                    if v not in groups.setdefault(key, []):
                        groups[key].append(v)
        return groups
    return {k: values_of(v) for k, v in attributes.items() if isinstance(v, list) and len(v) > 1}


def clean_options(groups: Mapping[str, list[str]], chosen: Mapping[str, str]) -> dict[str, str]:
    """The choice, checked: every group answered with one of its values, nothing else. Raises ValueError with a message."""
    unknown = set(chosen) - set(groups)
    if unknown:
        raise ValueError(f"Unknown option: {sorted(unknown)[0]}")
    out: dict[str, str] = {}
    for key, values in groups.items():
        value = str(chosen.get(key, "")).strip()
        if not value:
            raise ValueError(f"Choose a {key}")
        if value not in values:
            raise ValueError(f"{value} isn't one of the {key} choices")
        out[key] = value
    return out


def matches(variant_attributes: Mapping[str, Any], options: Mapping[str, str]) -> bool:
    return all(k in variant_attributes and v in values_of(variant_attributes[k]) for k, v in options.items())


@dataclass(frozen=True)
class Target:
    product_id: int  # the variant, or the product itself
    kind: str  # "restock" | "request"
    available: bool  # the combination can be bought now (no request needed: add it to the cart)


def resolve(product_id: int, product_buyable: bool, variants: list[tuple[int, Mapping[str, Any], bool]], options: Mapping[str, str]) -> Target:
    """`variants`: (id, attributes, buyable) for each published variant."""
    if variants:
        for vid, attrs, buyable in variants:
            if matches(attrs, options):
                return Target(vid, "restock", buyable)
        return Target(product_id, "request", False)  # a combination the shop doesn't make yet
    return Target(product_id, "restock", product_buyable)


def describe(options: Mapping[str, str]) -> str:
    """'Size: Large, Wood: Walnut' (empty when there are no options)."""
    return ", ".join(f"{k}: {v}" for k, v in options.items())
