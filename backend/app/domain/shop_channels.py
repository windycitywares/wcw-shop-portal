"""The external shops (marketplaces) the shop can connect to. One place for their ids and names.

(Not app/domain/channels.py, which is about where website visitors come from.)
"""

CHANNELS: dict[str, str] = {"etsy": "Etsy"}  # later: "amazon": "Amazon", "walmart": "Walmart"


def clean(channels: list[str]) -> list[str]:
    """Known channel ids, lowercase, once each, in the order of CHANNELS. Unknown ids are an error for the caller."""
    wanted = {c.strip().lower() for c in channels}
    unknown = wanted - set(CHANNELS)
    if unknown:
        raise ValueError(f"Unknown shop: {', '.join(sorted(unknown))}")
    return [c for c in CHANNELS if c in wanted]
