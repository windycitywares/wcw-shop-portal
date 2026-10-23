"""Editable wording for the customer emails: the built-in text, the owner's changes, a preview and a test send."""

from typing import Any

from app.core import mailer
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.domain import emailtext
from app.models.user import User
from app.services import audit
from app.services.settings import SettingsService

LABELS: dict[str, tuple[str, str]] = {
    "subscribe_confirmation": ("Newsletter sign-up", "Sent when someone subscribes (when the welcome offer is off, or they re-subscribe)."),
    "welcome_offer": ("Welcome offer", "Sent to a new subscriber with their personal discount code."),
    "account_welcome": ("New account", "Sent after someone creates an account."),
    "password_reset": ("Password reset", "Sent when someone asks to reset a password. The link is added by the shop."),
    "password_reset_no_account": ("Password reset: no account", "Sent when someone asks to reset a password for an address that has no account. It points them to sign up."),
    "order_received": ("Order received (waiting for payment)", "Sent when an order is placed but not paid yet."),
    "order_confirmation": ("Order confirmed", "Sent when payment is received."),
    "order_shipped": ("Order shipped", "Sent when the order has shipped, with tracking."),
    "order_delivered": ("Order delivered", "Sent when the order is marked delivered."),
    "order_cancelled": ("Order cancelled", "Sent when an order is cancelled."),
    "order_refunded": ("Refund issued", "Sent when a refund is made."),
}
PLACEHOLDER_HELP = {
    "number": "the order number", "amount": "the refunded amount", "percent": "the discount percent",
    "expires": "the date the code expires", "minutes": "how long the reset link works",
}
PARTS = (("subject", "Subject"), ("intro", "Opening message"), ("button", "Button text"), ("signoff", "Sign-off"))

SAMPLE: dict[str, Any] = {
    "name": "Ana", "number": "WCW-1042", "items": [{"title": "Hand-painted ceramic vase", "qty": 1, "total": "$48.00"}],
    "subtotal": "$48.00", "discount": None, "shipping": "$6.00", "tax": "$3.10", "total": "$57.10", "amount": "$57.10",
    "address": "Ana Perez\n12 Example Street\nChicago, IL 60601", "delivery_estimate": "October 30, 2026", "carrier": "USPS",
    "tracking_number": "9400 1000 0000 0000 0000 00", "tracking_url": "https://example.com/track", "instructions": "",
    "code": "WELCOME-AB12CD", "percent": 10, "expires": "November 30, 2026", "minutes": 60, "refund_note": True,
}


def _sample(kind: str, locale: str) -> dict[str, Any]:
    from app.services.emails import site_link

    return {**SAMPLE, "locale": locale, "link": site_link("/account/orders", locale), "account_url": site_link("/account", locale),
            "shop_url": site_link("/shop", locale), "signup_url": site_link("/login", locale) + "?mode=register", "unsubscribe_url": site_link("/unsubscribe", locale) + "?token=sample"}


def _clean(fields: dict[str, Any]) -> dict[str, str]:
    return {k: v.strip() for k, v in fields.items() if k in emailtext.FIELDS and isinstance(v, str) and v.strip()}


class EmailTemplateService:
    def __init__(self, session):
        self.session = session

    @staticmethod
    def _check(kind: str, language: str) -> None:
        if kind not in emailtext.EDITABLE:
            raise NotFoundError("Unknown email")
        if language not in emailtext.LOCALES:
            raise ValidationFailedError("Unknown language")

    async def catalog(self) -> list[dict]:
        saved = (await SettingsService(self.session).load()).email_templates.templates
        out = []
        for kind, placeholders in emailtext.EDITABLE.items():
            label, description = LABELS[kind]
            languages = {}
            for lang in emailtext.LOCALES:
                defaults: dict = {}
                emailtext.render(kind, _sample(kind, lang), overrides={}, capture=defaults)
                languages[lang] = {"defaults": defaults, "saved": (saved.get(kind) or {}).get(lang, {})}
            out.append({"kind": kind, "label": label, "description": description,
                        "placeholders": [{"name": p, "help": PLACEHOLDER_HELP.get(p, "")} for p in placeholders], "languages": languages})
        return out

    def preview(self, kind: str, language: str, fields: dict[str, Any]) -> dict:
        self._check(kind, language)
        rendered = emailtext.render(kind, _sample(kind, language), overrides={kind: {language: _clean(fields)}})
        return {"subject": rendered.subject, "html": rendered.html, "text": rendered.text}

    async def save(self, kind: str, language: str, fields: dict[str, Any], user: User) -> list[dict]:
        self._check(kind, language)
        settings = SettingsService(self.session)
        templates = {k: {l: dict(f) for l, f in v.items()} for k, v in (await settings.load()).email_templates.templates.items()}
        mine = _clean(fields)
        # Text identical to the built-in wording isn't an override: it would freeze that text against later improvements.
        defaults: dict = {}
        emailtext.render(kind, _sample(kind, language), overrides={}, capture=defaults)
        mine = {k: v for k, v in mine.items() if v != defaults.get(k)}
        if mine:
            templates.setdefault(kind, {})[language] = mine
        else:
            templates.get(kind, {}).pop(language, None)
            if not templates.get(kind):
                templates.pop(kind, None)
        await settings.update("email_templates", {"templates": templates}, user)
        return await self.catalog()

    async def send_test(self, kind: str, language: str, fields: dict[str, Any], user: User) -> str:
        data = self.preview(kind, language, fields)
        await mailer.send(mailer.Mail(to=user.email, subject="[Test] " + data["subject"], text=data["text"], html=data["html"]))
        audit.record(self.session, user, "email_template.test", "email_template", kind, f"Sent a test of the {kind} email", {})
        await self.session.commit()
        return user.email
