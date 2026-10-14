"""Payment providers. Each one starts a payment for an order and says what the shopper should do next."""

from app.services.payments.base import PaymentStart, ProviderError
from app.services.payments.manual import ManualProvider
from app.services.payments.stripe import StripeProvider
from app.services.payments.test import TestProvider

PROVIDERS = {"stripe": StripeProvider(), "manual": ManualProvider(), "test": TestProvider()}


def get_provider(name: str):
    provider = PROVIDERS.get(name)
    if provider is None:
        raise ProviderError(f"Unknown payment provider {name!r}")
    return provider


__all__ = ["PROVIDERS", "PaymentStart", "ProviderError", "get_provider"]
