"""Cleaning what the browser reports before it is stored.

Analytics must never hold personal data by accident, so everything that arrives is reduced here: page
addresses lose their query string and any private token, search terms that look like an email address or
a phone number are dropped, and free-form event data is limited to a few short values.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

LOCALE_PREFIX = re.compile(r"^/(es|nl)(?=/|$)")
# Pages whose address contains a secret (a private order link, a password-reset token)
PRIVATE_SEGMENTS = {"order": "/order/:token", "unsubscribe": "/unsubscribe", "reset-password": "/reset-password"}
MAX_PATH = 200
MAX_TERM = 80
MAX_DATA_KEYS = 6
MAX_DATA_TEXT = 120

EVENT_TYPES = frozenset({
    "page_view", "product_view", "search", "add_to_cart", "remove_from_cart", "view_cart", "begin_checkout",
    "wishlist_add", "newsletter_signup", "coupon_applied", "coupon_failed", "notify_me", "web_vital", "client_error",
    "recently_viewed_click", "recommendation_click", "share",
})
VITALS = frozenset({"LCP", "CLS", "INP", "FCP", "TTFB"})

_EMAIL = re.compile(r"\S+@\S+")
_DIGITS = re.compile(r"\d")


def clean_path(raw: str | None) -> str | None:
    """'/es/product/urn?x=1#top' -> '/product/urn'. Private links collapse to a placeholder."""
    if not raw:
        return None
    raw = raw.strip()
    if "://" in re.split(r"[?#]", raw, maxsplit=1)[0]:  # a full address: keep only its path
        try:
            path = urlsplit(raw).path
        except ValueError:
            return None
    else:
        path = re.split(r"[?#]", raw, maxsplit=1)[0]
    path = re.sub(r"/{2,}", "/", path)
    if not path.startswith("/"):
        return None
    path = LOCALE_PREFIX.sub("", path) or "/"
    parts = [p for p in path.split("/") if p]
    if parts and parts[0] in PRIVATE_SEGMENTS:
        return PRIVATE_SEGMENTS[parts[0]]
    if len(path) > 1:
        path = path.rstrip("/")
    return path[:MAX_PATH]


def clean_term(raw: Any) -> str | None:
    """A search term worth keeping: short, lower-case, and not something a person typed about themselves."""
    if not isinstance(raw, str):
        return None
    term = " ".join(raw.lower().split())[:MAX_TERM]
    if len(term) < 2 or _EMAIL.search(term) or len(_DIGITS.findall(term)) >= 7:
        return None
    return term


def clean_data(data: dict[str, Any] | None) -> dict[str, Any]:
    """Keep a handful of short scalar values. Nested objects and long text are dropped."""
    out: dict[str, Any] = {}
    for key, value in (data or {}).items():
        if len(out) >= MAX_DATA_KEYS:
            break
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,23}", key):
            continue
        if isinstance(value, bool) or value is None:
            out[key] = value
        elif isinstance(value, (int, float)):
            if abs(value) < 1e12:
                out[key] = value
        elif isinstance(value, str):
            text = value.strip()[:MAX_DATA_TEXT]
            if _EMAIL.search(text):
                continue
            out[key] = text
    return out


def clean_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Validate one event from the browser. Returns the row to store, or None to drop it."""
    kind = event.get("type")
    if kind not in EVENT_TYPES:
        return None
    data = clean_data(event.get("data"))
    row: dict[str, Any] = {"type": kind, "path": clean_path(event.get("path")), "product_id": event.get("product_id"), "value": event.get("value"), "data": data}
    if kind == "search":
        term = clean_term(data.get("q"))
        if term is None:
            return None
        data["q"] = term
        results = data.get("results")
        data["results"] = int(results) if isinstance(results, (int, float)) and not isinstance(results, bool) and 0 <= results < 1e6 else None
    elif kind == "web_vital":
        name = data.get("name")
        value = row["value"]
        if name not in VITALS or value is None or value < 0 or value > 600_000:
            return None
        data = {"name": name}
        row["data"] = data
    elif kind in ("product_view", "add_to_cart", "remove_from_cart", "wishlist_add", "notify_me") and row["product_id"] is None:
        return None
    elif kind == "client_error":
        row["data"] = {"message": str(data.get("message", ""))[:MAX_DATA_TEXT]}
    return row
