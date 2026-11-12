"""A pretend card payment for Test mode: the shopper is sent to a card page, types a test card and pays, exactly as
with Stripe's hosted page, but no card network is involved and nothing is charged.

Used while Test mode is on and Stripe has no test keys (with test keys the real Stripe test checkout is used).
Never available on live data in production. The card number is looked at and thrown away; it is never stored."""

from dataclasses import dataclass
from datetime import date

from app.core.config import get_settings
from app.services.payments.base import PaymentStart, ProviderError

# Stripe's published test numbers and what they do. Anything else is "not a test card".
OUTCOMES = {
    "4242424242424242": None,  # Visa, succeeds
    "5555555555554444": None,  # Mastercard, succeeds
    "378282246310005": None,  # American Express, succeeds
    "4000000000000002": "Your card was declined.",
    "4000000000009995": "Your card has insufficient funds.",
    "4000000000000069": "Your card has expired.",
    "4000000000000127": "Your card's security code is incorrect.",
}
NOT_A_TEST_CARD = "This is a test checkout. Use a test card, for example 4242 4242 4242 4242."


@dataclass(frozen=True)
class CardResult:
    paid: bool
    message: str | None = None


def check_card(number: str, exp_month: int, exp_year: int, cvc: str, today: date | None = None) -> CardResult:
    """Decide the outcome of a test payment. Pure: no I/O and nothing kept."""
    digits = "".join(ch for ch in number if ch.isdigit())
    if digits not in OUTCOMES:
        return CardResult(False, NOT_A_TEST_CARD)
    today = today or date.today()
    year = exp_year + 2000 if exp_year < 100 else exp_year
    if not 1 <= exp_month <= 12 or (year, exp_month) < (today.year, today.month):
        return CardResult(False, "Your card's expiry date is in the past.")
    if not cvc.isdigit() or len(cvc) != (4 if digits == "378282246310005" else 3):
        return CardResult(False, "Your card's security code is incomplete.")
    reason = OUTCOMES[digits]
    return CardResult(reason is None, reason)


def available() -> bool:
    from app.core import appmode

    return not get_settings().is_production or appmode.is_test()


class TestCardProvider:
    __test__ = False  # not a unittest class
    name = "test_card"

    async def start(self, order, return_urls: dict[str, str], lang: str, attempt: int = 1) -> PaymentStart:
        from app.services import emails

        if not available():
            raise ProviderError("The test card payment is disabled on live data in production")
        url = emails.site_link(f"/order/{order.access_token}/test-payment", lang)
        return PaymentStart(status="redirect", provider_ref=f"test_{order.number}", redirect_url=url, raw={"test": True})

    async def refund(self, order, amount, reason: str | None) -> dict:
        return {"test": True}
