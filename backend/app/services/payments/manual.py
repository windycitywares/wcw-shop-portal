from app.services.payments.base import PaymentStart


class ManualProvider:
    """The old "pay later" flow: the order is saved and the owner collects payment, then marks it paid.

    Checkout no longer offers it (an order should not be placed before it is paid), but orders taken
    while it did are still waiting, and staff still use the same path to record a payment that arrived
    outside the card flow (bank transfer, cash, check).
    """

    name = "manual"

    async def start(self, order, return_urls: dict[str, str], lang: str, attempt: int = 1) -> PaymentStart:
        return PaymentStart(status="pending")

    async def refund(self, order, amount, reason: str | None) -> dict:
        return {"recorded_manually": True}
