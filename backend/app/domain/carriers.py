"""Tracking links for the carriers a small shop uses. Staff can always paste their own link instead."""

from urllib.parse import quote

CARRIERS: dict[str, str] = {
    "USPS": "https://tools.usps.com/go/TrackConfirmAction?tLabels={n}",
    "UPS": "https://www.ups.com/track?tracknum={n}",
    "FedEx": "https://www.fedex.com/fedextrack/?trknbr={n}",
    "DHL": "https://www.dhl.com/us-en/home/tracking.html?tracking-id={n}",
}


def canonical_carrier(name: str | None) -> str | None:
    """'usps ' -> 'USPS', 'Fedex' -> 'FedEx'. Unknown carriers keep the text they were given (trimmed)."""
    cleaned = " ".join((name or "").split())
    if not cleaned:
        return None
    for known in CARRIERS:
        if known.lower() == cleaned.lower():
            return known
    return cleaned[:60]


def tracking_url(carrier: str | None, number: str | None) -> str | None:
    template = CARRIERS.get(canonical_carrier(carrier) or "")
    cleaned = "".join((number or "").split())
    if not template or not cleaned:
        return None
    return template.format(n=quote(cleaned, safe=""))
