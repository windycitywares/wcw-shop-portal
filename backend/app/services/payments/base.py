from dataclasses import dataclass, field
from typing import Any


class ProviderError(Exception):
    """The payment provider refused or couldn't be reached. The message is safe to log, not to show."""


@dataclass
class PaymentStart:
    """What happened when a payment was started."""

    status: str  # paid | pending | redirect
    provider_ref: str | None = None
    redirect_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
