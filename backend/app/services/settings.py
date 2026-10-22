"""Load and save store settings; turn them into the plain configs the pricing engine uses."""

import logging
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import captcha
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.domain.pricing import ShippingConfig, TaxConfig
from app.models.commerce import StoreSetting
from app.models.user import User
from app.schemas.settings import GROUPS, AdminSettingsOut, PublicConfig, StoreSettings
from app.services import audit
from app.services.ttl import TtlCache

log = logging.getLogger("wcw.settings")
_cache: TtlCache[StoreSettings] = TtlCache(ttl=20)


def clear_cache() -> None:
    _cache.clear()


def shipping_config(s: StoreSettings) -> ShippingConfig:
    sh = s.shipping
    return ShippingConfig(
        flat_rate=sh.flat_rate,
        free_threshold=sh.free_threshold,
        international_rate=sh.international_rate,
        allowed_countries=tuple(sh.allowed_countries),
    )


def tax_config(s: StoreSettings) -> TaxConfig:
    t = s.tax
    return TaxConfig(enabled=t.enabled, rate_percent=t.rate_percent, regions=tuple(t.regions), shipping_taxable=t.shipping_taxable)


def payment_methods(s: StoreSettings) -> list[str]:
    """Payment choices offered at checkout, best first."""
    from app.core import appmode
    from app.services.payments.stripe import secret_key

    app = get_settings()
    methods: list[str] = []
    if secret_key():
        methods.append("stripe")
    if not app.is_production or appmode.is_test():
        methods.append("test")  # no-charge payment for development, the browser tests and Test mode
    return methods


def status_flags() -> dict[str, bool]:
    app = get_settings()
    return {
        "production": app.is_production,
        "stripe_configured": bool(app.stripe_secret_key),
        "stripe_webhook_configured": bool(app.stripe_webhook_secret),
        "email_configured": bool(app.smtp_host),
        "captcha_configured": bool(app.turnstile_secret),
    }


def public_config(s: StoreSettings, lang: str) -> PublicConfig:
    app = get_settings()
    sh = s.shipping
    text = s.general.announcement.get(lang) or s.general.announcement.get("en")
    return PublicConfig(
        free_shipping_threshold=float(sh.free_threshold) if sh.free_threshold is not None else None,
        flat_shipping_rate=float(sh.flat_rate),
        international_shipping=sh.international_rate is not None,
        shipping_countries=sh.allowed_countries,
        delivery_days=(sh.handling_days_min + sh.transit_days_min, sh.handling_days_max + sh.transit_days_max),
        handling_days=(sh.handling_days_min, sh.handling_days_max),
        transit_days=(sh.transit_days_min, sh.transit_days_max),
        tax_enabled=s.tax.enabled and s.tax.rate_percent > 0,
        tax_label=s.tax.label,
        announcement=text if s.general.announcement_enabled and text else None,
        welcome_percent=s.welcome.percent if s.welcome.enabled else None,
        payment_methods=payment_methods(s),
        guest_checkout=s.general.guest_checkout,
        reminders_opt_in=not s.cart_recovery.email_everyone,
        reminders_signed_in=s.cart_recovery.enabled and s.cart_recovery.remind_signed_in,
        max_quantity_per_line=s.general.max_quantity_per_line,
        low_stock_threshold=s.general.low_stock_threshold,
        analytics_enabled=s.analytics.enabled,
        turnstile_site_key=captcha.public_site_key(app),
    )


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(str(p) for p in err["loc"])
    return f"{where}: {err['msg']}" if where else err["msg"]


class SettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def load(self) -> StoreSettings:
        cached = _cache.get()
        if cached is not None:
            return cached
        rows = (await self.session.execute(select(StoreSetting))).scalars().all()
        groups = {}
        for row in rows:
            model = GROUPS.get(row.key)
            if model is None:
                continue
            try:
                groups[row.key] = model.model_validate(row.value or {})
            except ValidationError:
                log.warning("Ignoring invalid stored settings for %s", row.key)
        return _cache.set(StoreSettings(**groups))

    async def setup_checklist(self) -> dict[str, bool]:
        """What has to be in place before the store can sell with confidence (feeds the dashboard and the suggestions)."""
        s = await self.load()
        saved = set((await self.session.execute(select(StoreSetting.key))).scalars().all())
        flags = status_flags()
        return {
            "payments_live": flags["stripe_configured"],
            "shipping_configured": "shipping" in saved,
            "tax_configured": s.tax.enabled and s.tax.rate_percent > 0,
            "email_configured": flags["email_configured"],
            "captcha_configured": flags["captcha_configured"],
            "welcome_offer": s.welcome.enabled,
        }

    async def admin_view(self) -> AdminSettingsOut:
        return AdminSettingsOut(settings=await self.load(), status=status_flags())

    async def update(self, group: str, patch: dict, user: User) -> AdminSettingsOut:
        model = GROUPS.get(group)
        if model is None:
            raise NotFoundError("Unknown settings group")
        unknown = set(patch) - set(model.model_fields)
        if unknown:
            raise ValidationFailedError(f"Unknown setting: {', '.join(sorted(unknown))}")
        current = getattr(await self.load(), group).model_dump(mode="json")
        try:
            validated = model.model_validate({**current, **patch})
        except ValidationError as exc:
            raise ValidationFailedError(_first_error(exc)) from exc
        value = validated.model_dump(mode="json")
        row = await self.session.get(StoreSetting, group)
        if row is None:
            self.session.add(StoreSetting(key=group, value=value, updated_by_id=user.id))
        else:
            row.value = value
            row.updated_by_id = user.id
        changed = {k: value[k] for k in value if current.get(k) != value[k]}
        audit.record(self.session, user, "settings.update", "settings", group, f"Changed {group} settings", {"changed": changed})
        await self.session.commit()
        clear_cache()
        return await self.admin_view()


def decimal_or_none(value: float | Decimal | None) -> Decimal | None:
    return None if value is None else Decimal(str(value))
