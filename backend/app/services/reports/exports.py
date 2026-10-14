"""CSV files for the reports. Each function takes the finished report and returns (header, rows)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.domain.csvsafe import to_csv

Table = tuple[list[str], list[list[Any]]]


def pct(value: float | None) -> float | None:
    """A rate (0.042) as a percentage number (4.2) for spreadsheets."""
    return None if value is None else round(value * 100, 2)


def sales(r: dict[str, Any]) -> Table:
    return (
        ["Period starting", "Orders", "Gross sales", "Refunds", "Net revenue"],
        [[p["bucket"], p["orders"], p["gross"], p["refunds"], p["net"]] for p in r["series"]],
    )


def products(r: dict[str, Any]) -> Table:
    header = ["Product", "SKU", "Class", "Units sold", "Orders", "Revenue", "Profit", "Margin %", "Views", "Visitors", "Added to cart", "Wishlist adds",
              "Conversion %", "Return rate %", "In stock", "Rating", "Reviews"]
    rows = [
        [p["title"], p["sku"], p["abc"], p["units"], p["orders"], p["merchandise"], p["profit"], pct(p["margin"]), p["views"], p["viewers"], p["carted"],
         p["wishlist_adds"], pct(p["conversion"]), pct(p["return_rate"]), p["stock"], p["rating"], p["rating_count"]]
        for p in r["products"]
    ]
    return header, rows


def traffic(r: dict[str, Any]) -> Table:
    return (
        ["Source", "Visits", "Visitors", "Share of visits %", "Bounce rate %", "Orders", "Revenue", "Conversion %", "Revenue per visit"],
        [[c["channel"], c["sessions"], c["visitors"], pct(c["share"]), pct(c["bounce_rate"]), c["orders"], c["revenue"], pct(c["conversion"]), c["revenue_per_visit"]]
         for c in r["channels"]],
    )


def funnel(r: dict[str, Any]) -> Table:
    return (
        ["Step", "Visits", "Of previous step %", "Of all visits %", "Lost"],
        [[s["label"], s["count"], pct(s["of_previous"]), pct(s["of_total"]), s["lost"]] for s in r["steps"]],
    )


def customers(r: dict[str, Any]) -> Table:
    return (
        ["Segment", "Customers", "Revenue", "Share of revenue %", "What it means"],
        [[s["label"], s["customers"], s["revenue"], pct(s["revenue_share"]), s["help"]] for s in r["segments"]],
    )


def promotions(r: dict[str, Any]) -> Table:
    return (
        ["Code", "Source", "Type", "Orders", "Discount given", "Revenue", "Revenue per $1 of discount"],
        [[c["code"], c["source"], c["kind"], c["orders"], c["discount"], c["revenue"], c["return_per_dollar"]] for c in r["coupons"]],
    )


def inventory(r: dict[str, Any]) -> Table:
    header = ["Product", "SKU", "Status", "In stock", "Sold (30 days)", "Sold (90 days)", "Days of cover", "Waiting for restock", "Cost", "Price",
              "Stock value at cost", "Suggested reorder"]
    rows = [
        [i["title"], i["sku"], i["status"], i["stock"], i["sold_30d"], i["sold_90d"], i["days_of_cover"], i["waiting"], i["cost"], i["price"],
         i["value_at_cost"], i["reorder"]]
        for i in r["items"]
    ]
    return header, rows


def catalog(r: dict[str, Any]) -> Table:
    return ["Product", "Score", "To fix"], [[w["title"], w["score"], "; ".join(w["problems"])] for w in r["worst"]]


EXPORTS: dict[str, tuple[str, Callable[[dict[str, Any]], Table]]] = {
    "sales": ("wcw-sales", sales), "products": ("wcw-products", products), "traffic": ("wcw-traffic-sources", traffic),
    "funnel": ("wcw-funnel", funnel), "customers": ("wcw-customer-segments", customers), "promotions": ("wcw-coupons", promotions),
    "inventory": ("wcw-inventory", inventory), "catalog": ("wcw-catalog-health", catalog),
}


def render(kind: str, report: dict[str, Any]) -> tuple[str, str]:
    """(file name stem, csv text)"""
    stem, build = EXPORTS[kind]
    header, rows = build(report)
    return stem, to_csv(header, rows)
