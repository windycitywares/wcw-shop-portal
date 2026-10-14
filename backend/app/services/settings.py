"""Store settings (with defaults in code), payment options and the checklist before checkout opens."""

import logging

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ValidationFailedError
from app.models.user import User
from app.payments import stripe
from app.repositories.commerce import SettingRepository, ShippingRepository, TaxRepository
from app.schemas.commerce import (
    PaymentOption,
    ReadinessItem,
    ShopConfig,
    StoreSettings,
    StoreSettingsOut,
    StoreSettingsPatch,
    WelcomeOffer,
)

log = logging.getLogger("wcw.settings")


class SettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SettingRepository(session)
        self.shipping = ShippingRepository(session)
        self.taxes = TaxRepository(session)

    async def load(self) -> StoreSettings:
        stored = await self.repo.all()
        known = {k: v for k, v in stored.items() if k in StoreSettings.model_fields}
        try:
            return StoreSettings.model_validate(known)
        except ValidationError:
            log.exception("Stored settings are invalid; using defaults for the invalid ones")
            valid: dict = {}
            for key, value in known.items():
                try:
                    StoreSettings.model_validate({key: value})
                    valid[key] = value
                except ValidationError:
                    continue
            return StoreSettings.model_validate(valid)

    # -- what can be offered ------------------------------------------
    @staticmethod
    def payment_options(cfg: StoreSettings) -> list[PaymentOption]:
        options: list[PaymentOption] = []
        if cfg.stripe_enabled and stripe.configured():
            options.append(PaymentOption(id="stripe", label="Credit or debit card", description="Pay securely on Stripe"))
        if cfg.offline_enabled:
            options.append(PaymentOption(id="offline", label=cfg.offline_label))
        if not get_settings().is_production:
            options.append(PaymentOption(id="test", label="Test payment", description="No charge. Only shown while the site is in development."))
        return options

    async def readiness(self, cfg: StoreSettings) -> list[ReadinessItem]:
        methods = await self.shipping.list_all(active_only=True)
        rates = await self.taxes.list_all(active_only=True)
        s = get_settings()
        return [
            ReadinessItem(id="shipping", ok=bool(methods), text="At least one shipping method is switched on"),
            ReadinessItem(id="payment", ok=bool(self.payment_options(cfg)),
                          text="A way to pay is available: cards through Stripe, or pay-by-invoice"),
            ReadinessItem(id="alerts", ok=bool(cfg.order_alert_email or s.contact_to or s.admin_email),
                          text="An email address receives new-order alerts"),
            ReadinessItem(id="tax", ok=bool(rates), required=False,
                          text="Sales tax rates are set up for the places you must collect it"),
        ]

    async def admin_view(self) -> StoreSettingsOut:
        cfg = await self.load()
        return StoreSettingsOut(
            **cfg.model_dump(),
            stripe_configured=stripe.configured(),
            test_payments_available=not get_settings().is_production,
            readiness=await self.readiness(cfg),
        )

    async def public_config(self) -> ShopConfig:
        cfg = await self.load()
        methods = await self.shipping.list_all(active_only=True)
        thresholds = [m.free_over for m in methods if m.free_over is not None and m.price > 0]
        countries: list[str] | None = None
        if methods and all(m.countries for m in methods):
            countries = sorted({c for m in methods for c in m.countries})
        offer = None
        if cfg.welcome_enabled:
            offer = WelcomeOffer(kind=cfg.welcome_kind, value=cfg.welcome_value, min_subtotal=cfg.welcome_min_subtotal)
        return ShopConfig(
            checkout_enabled=cfg.checkout_enabled, payment_options=self.payment_options(cfg),
            free_shipping_threshold=min(thresholds) if thresholds else None,
            shipping_countries=countries, welcome_offer=offer,
        )

    # -- changes --------------------------------------------------------
    async def update(self, patch: StoreSettingsPatch, user: User) -> StoreSettingsOut:
        changes = patch.model_dump(exclude_unset=True)
        current = await self.load()
        merged = {**current.model_dump(), **changes}
        try:
            new = StoreSettings.model_validate(merged)
        except ValidationError as exc:
            raise ValidationFailedError(exc.errors()[0]["msg"].removeprefix("Value error, ")) from exc
        if changes.get("checkout_enabled") and not current.checkout_enabled:
            missing = [item.text for item in await self.readiness(new) if item.required and not item.ok]
            if missing:
                raise ValidationFailedError("Checkout can't be switched on yet. Still to do: " + "; ".join(missing) + ".")
        stored = new.model_dump(mode="json")
        for key in changes:
            await self.repo.upsert(key, stored[key], user.id)
        await self.session.commit()
        return await self.admin_view()
