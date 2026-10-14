from app.core.config import get_settings
from app.services.payments.base import PaymentStart, ProviderError


class TestProvider:
    """A no-charge payment for development and the browser tests. Never available in production."""

    __test__ = False  # not a unittest class
    name = "test"

    async def start(self, order, return_urls: dict[str, str], lang: str, attempt: int = 1) -> PaymentStart:
        if get_settings().is_production:
            raise ProviderError("The test payment provider is disabled in production")
        return PaymentStart(status="paid", provider_ref=f"test_{order.number}")

    async def refund(self, order, amount, reason: str | None) -> dict:
        return {"test": True}
