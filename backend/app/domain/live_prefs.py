"""How a member of staff wants to hear about live updates. Pure: no database.

Events are grouped into categories a person recognises ("New orders", "Messages" …); for each one they choose a
pop-up in the admin, a sound, and/or a desktop alert (while the admin is in a background tab). Only what a person
changed is stored (users.notification_prefs); `with_defaults` fills in the rest, so a new category added later
starts with its default for everyone.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CATEGORIES: dict[str, str] = {
    "orders_new": "New orders",
    "orders_payments": "Payments and refunds",
    "orders_status": "Order status changes (shipped, delivered, cancelled)",
    "messages": "Contact messages",
    "customers": "New customer accounts",
    "newsletter": "Newsletter sign-ups and unsubscribes",
    "reviews": "New reviews",
    "stock": "Back-in-stock and special requests",
    "products": "Product changes by other staff",
    "backups": "Failed backups",
}
# What a new member of staff gets: the things worth interrupting for.
DEFAULT_CHANNELS: dict[str, dict[str, bool]] = {
    "orders_new": {"popup": True, "sound": True, "desktop": False},
    "messages": {"popup": True, "sound": False, "desktop": False},
    "backups": {"popup": True, "sound": False, "desktop": False},
}
Sound = Literal["chime", "bell", "pop"]


class Channels(BaseModel):
    popup: bool = False
    sound: bool = False
    desktop: bool = False


class NotificationPrefs(BaseModel):
    categories: dict[str, Channels] = Field(default_factory=dict)
    sound: Sound = "chime"
    volume: int = Field(default=70, ge=0, le=100)
    refresh_bars: bool = True  # "N updates · Refresh" above lists, "changed since you opened it" on records
    new_version: bool = True  # "A new version of the admin is out · Refresh"


def with_defaults(stored: dict[str, Any] | None) -> NotificationPrefs:
    """The stored choices over the defaults; unknown categories and bad values are dropped, not errors."""
    stored = stored or {}
    cats = stored.get("categories") if isinstance(stored.get("categories"), dict) else {}
    merged: dict[str, Channels] = {}
    for key in CATEGORIES:
        base = Channels(**DEFAULT_CHANNELS.get(key, {}))
        mine = cats.get(key)
        if isinstance(mine, dict):
            base = base.model_copy(update={k: bool(v) for k, v in mine.items() if k in Channels.model_fields})
        merged[key] = base
    rest = {k: stored[k] for k in ("sound", "volume", "refresh_bars", "new_version") if k in stored}
    try:
        return NotificationPrefs(categories=merged, **rest)
    except ValueError:
        return NotificationPrefs(categories=merged)


def to_store(prefs: NotificationPrefs) -> dict[str, Any]:
    """Only the categories known today, so the column never grows with junk."""
    data = prefs.model_dump()
    data["categories"] = {k: v for k, v in data["categories"].items() if k in CATEGORIES}
    return data
