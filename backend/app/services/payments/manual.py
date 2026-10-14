from app.services.payments.base import PaymentStart


class ManualProvider:
    """"Pay later": the order is saved and the owner collects payment (invoice, bank transfer, phone) then marks it paid."""

    name = "manual"

    async def start(self, order, return_urls: dict[str, str], lang: str, attempt: int = 1) -> PaymentStart:
        return PaymentStart(status="pending")

    async def refund(self, order, amount, reason: str | None) -> dict:
        return {"recorded_manually": True}
