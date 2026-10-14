"""Emails about orders and coupons, in the customer's language (en, es, nl).

Plain text first, with a light HTML version in the shop's navy and gold. Sending never blocks or breaks
an order: failures are logged by the mailer and swallowed here.
"""

import logging
from decimal import Decimal
from html import escape

from app.core import mailer
from app.core.config import get_settings
from app.models.order import Order

log = logging.getLogger("wcw.order_emails")

NAVY = "#1f3a4d"
GOLD = "#b8893b"

T = {
    "en": {
        "confirm_subject": "Your WindyCityWares order {number}",
        "confirm_intro": "Thank you for your order. We'll take good care of it. Here is what you ordered:",
        "hi": "Hi{name},",
        "subtotal": "Subtotal", "discount": "Discount", "shipping": "Shipping", "tax": "Tax", "total": "Total",
        "free": "Free", "ship_to": "Shipping to", "qty": "Qty",
        "paid_note": "We've received your payment.",
        "pending_note": "Your order is waiting for payment.",
        "view": "You can follow your order here:",
        "questions": "Questions? Just reply to this email.",
        "signoff": "With care,\nWindyCityWares",
        "shipped_subject": "Your order {number} is on its way",
        "shipped_intro": "Good news: your order has shipped.",
        "carrier": "Carrier", "tracking": "Tracking number",
        "refund_subject": "Refund for order {number}",
        "refund_intro": "We've refunded {amount} for your order. It can take 5 to 10 business days to show up on your statement.",
        "reason": "Note",
        "cancel_subject": "Your order {number} was cancelled",
        "cancel_intro": "Your order has been cancelled.",
        "cancel_refund": "Any payment will be refunded to the way you paid.",
        "coupon_subject": "A little something from WindyCityWares",
        "coupon_welcome": "Welcome, and thank you for subscribing. Here is a code for {offer} on your first order:",
        "coupon_personal": "We'd like to offer you {offer}. Use this code at checkout:",
        "coupon_valid": "Valid until {date}.",
        "coupon_use": "Enter it in the cart or at checkout.",
        "offer_percent": "{value}% off", "offer_fixed": "{value} off", "offer_shipping": "free shipping",
        "min_spend": "On orders over {amount}.",
        "button": "View your order",
    },
    "es": {
        "confirm_subject": "Tu pedido {number} de WindyCityWares",
        "confirm_intro": "Gracias por tu pedido. Lo cuidaremos con esmero. Esto es lo que pediste:",
        "hi": "Hola{name}:",
        "subtotal": "Subtotal", "discount": "Descuento", "shipping": "Envío", "tax": "Impuestos", "total": "Total",
        "free": "Gratis", "ship_to": "Enviar a", "qty": "Cant.",
        "paid_note": "Hemos recibido tu pago.",
        "pending_note": "Tu pedido está esperando el pago.",
        "view": "Puedes seguir tu pedido aquí:",
        "questions": "¿Preguntas? Solo responde a este correo.",
        "signoff": "Con cariño,\nWindyCityWares",
        "shipped_subject": "Tu pedido {number} va en camino",
        "shipped_intro": "Buenas noticias: tu pedido ya fue enviado.",
        "carrier": "Transportista", "tracking": "Número de seguimiento",
        "refund_subject": "Reembolso del pedido {number}",
        "refund_intro": "Hemos reembolsado {amount} de tu pedido. Puede tardar de 5 a 10 días hábiles en aparecer en tu estado de cuenta.",
        "reason": "Nota",
        "cancel_subject": "Tu pedido {number} fue cancelado",
        "cancel_intro": "Tu pedido ha sido cancelado.",
        "cancel_refund": "Cualquier pago se reembolsará por el mismo medio con el que pagaste.",
        "coupon_subject": "Un detalle de WindyCityWares",
        "coupon_welcome": "Te damos la bienvenida y gracias por suscribirte. Aquí tienes un código de {offer} en tu primer pedido:",
        "coupon_personal": "Queremos ofrecerte {offer}. Usa este código al pagar:",
        "coupon_valid": "Válido hasta el {date}.",
        "coupon_use": "Escríbelo en el carrito o al pagar.",
        "offer_percent": "{value}% de descuento", "offer_fixed": "{value} de descuento", "offer_shipping": "envío gratis",
        "min_spend": "En pedidos de más de {amount}.",
        "button": "Ver tu pedido",
    },
    "nl": {
        "confirm_subject": "Je bestelling {number} bij WindyCityWares",
        "confirm_intro": "Bedankt voor je bestelling. We zorgen er met aandacht voor. Dit heb je besteld:",
        "hi": "Hallo{name},",
        "subtotal": "Subtotaal", "discount": "Korting", "shipping": "Verzending", "tax": "Belasting", "total": "Totaal",
        "free": "Gratis", "ship_to": "Verzenden naar", "qty": "Aantal",
        "paid_note": "We hebben je betaling ontvangen.",
        "pending_note": "Je bestelling wacht op betaling.",
        "view": "Je kunt je bestelling hier volgen:",
        "questions": "Vragen? Antwoord gewoon op deze e-mail.",
        "signoff": "Met zorg,\nWindyCityWares",
        "shipped_subject": "Je bestelling {number} is onderweg",
        "shipped_intro": "Goed nieuws: je bestelling is verzonden.",
        "carrier": "Vervoerder", "tracking": "Trackingnummer",
        "refund_subject": "Terugbetaling voor bestelling {number}",
        "refund_intro": "We hebben {amount} van je bestelling terugbetaald. Het kan 5 tot 10 werkdagen duren voordat het op je afschrift staat.",
        "reason": "Opmerking",
        "cancel_subject": "Je bestelling {number} is geannuleerd",
        "cancel_intro": "Je bestelling is geannuleerd.",
        "cancel_refund": "Een eventuele betaling wordt terugbetaald op de manier waarop je hebt betaald.",
        "coupon_subject": "Een attentie van WindyCityWares",
        "coupon_welcome": "Welkom, en bedankt voor je inschrijving. Hier is een code voor {offer} op je eerste bestelling:",
        "coupon_personal": "We willen je graag {offer} aanbieden. Gebruik deze code bij het afrekenen:",
        "coupon_valid": "Geldig tot {date}.",
        "coupon_use": "Vul de code in bij de winkelwagen of bij het afrekenen.",
        "offer_percent": "{value}% korting", "offer_fixed": "{value} korting", "offer_shipping": "gratis verzending",
        "min_spend": "Bij bestellingen boven {amount}.",
        "button": "Bekijk je bestelling",
    },
}


def tr(locale: str | None) -> dict[str, str]:
    return T.get(locale or "en", T["en"])


def money(amount: Decimal | float | int, locale: str | None = "en", currency: str = "USD") -> str:
    symbol = "$" if currency == "USD" else f"{currency} "
    text = f"{Decimal(amount):,.2f}"
    if locale == "nl":
        text = text.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{symbol} {text}"
    return f"{symbol}{text}"


def localized(locale: str | None, path: str) -> str:
    base = get_settings().site_url.rstrip("/")
    return f"{base}{path}" if not locale or locale == "en" else f"{base}/{locale}{path}"


def order_link(order: Order) -> str:
    return f"{localized(order.locale, f'/order/{order.number}')}?token={order.access_token}"


def _first_name(order: Order) -> str:
    name = (order.shipping_address or {}).get("full_name") or ""
    return f" {name.split()[0]}" if name else ""


def _address_lines(address: dict | None) -> list[str]:
    if not address:
        return []
    city = " ".join(x for x in [address.get("city"), address.get("region"), address.get("postal_code")] if x)
    return [x for x in [address.get("full_name"), address.get("company"), address.get("line1"), address.get("line2"), city, address.get("country")] if x]


def _shell(title: str, body_html: str, button: tuple[str, str] | None, foot: str) -> str:
    cta = (
        f'<p style="margin:28px 0"><a href="{escape(button[1])}" style="background:{NAVY};color:#fff;text-decoration:none;'
        f'padding:12px 22px;border-radius:6px;display:inline-block">{escape(button[0])}</a></p>'
        if button else ""
    )
    return (
        f'<div style="background:#f4f2ee;padding:24px 12px;font-family:Georgia,serif;color:#222">'
        f'<div style="max-width:560px;margin:0 auto;background:#fff;border-radius:8px;overflow:hidden">'
        f'<div style="background:{NAVY};padding:18px 28px;color:#fff;font-size:20px;letter-spacing:.3px">'
        f'Windy<span style="color:{GOLD}">City</span>Wares</div>'
        f'<div style="padding:28px;font-size:16px;line-height:1.55"><h1 style="font-size:22px;margin:0 0 16px;font-weight:normal">{escape(title)}</h1>'
        f'{body_html}{cta}<p style="color:#666;font-size:14px;white-space:pre-line">{escape(foot)}</p></div></div></div>'
    )


def _order_table(order: Order, tx: dict[str, str]) -> tuple[str, str]:
    """(text, html) for the lines and totals."""
    loc = order.locale
    lines = [f"{i.quantity} x {i.title}  {money(i.line_total - i.discount, loc, order.currency)}" for i in order.items]
    rows = "".join(
        f'<tr><td style="padding:6px 0">{i.quantity} × {escape(i.title)}</td>'
        f'<td style="padding:6px 0;text-align:right;white-space:nowrap">{money(i.line_total - i.discount, loc, order.currency)}</td></tr>'
        for i in order.items
    )
    totals = [(tx["subtotal"], money(order.subtotal, loc, order.currency))]
    if order.discount_total:
        totals.append((tx["discount"] + (f" ({order.coupon_code})" if order.coupon_code else ""), "−" + money(order.discount_total, loc, order.currency)))
    totals.append((tx["shipping"], money(order.shipping_total, loc, order.currency) if order.shipping_total else tx["free"]))
    if order.tax_total:
        totals.append((tx["tax"], money(order.tax_total, loc, order.currency)))
    totals.append((tx["total"], money(order.grand_total, loc, order.currency)))
    text = "\n".join(lines) + "\n\n" + "\n".join(f"{k}: {v}" for k, v in totals)
    html = (
        f'<table style="width:100%;border-collapse:collapse;border-top:1px solid #e5e0d8;border-bottom:1px solid #e5e0d8;margin:16px 0">{rows}</table>'
        f'<table style="width:100%;border-collapse:collapse">'
        + "".join(
            f'<tr><td style="padding:3px 0;{"font-weight:bold" if k == tx["total"] else "color:#555"}">{escape(k)}</td>'
            f'<td style="padding:3px 0;text-align:right;{"font-weight:bold" if k == tx["total"] else ""}">{escape(v)}</td></tr>'
            for k, v in totals
        )
        + "</table>"
    )
    return text, html


async def _send(mail: mailer.Mail) -> None:
    try:
        await mailer.send(mail)
    except mailer.MailError:
        pass  # logged by the mailer; an email problem never fails an order


async def order_confirmation(order: Order, *, paid: bool, offline_instructions: str | None = None) -> None:
    tx = tr(order.locale)
    table_text, table_html = _order_table(order, tx)
    note = tx["paid_note"] if paid else tx["pending_note"]
    if not paid and offline_instructions:
        note += "\n\n" + offline_instructions
    address = _address_lines(order.shipping_address)
    link = order_link(order)
    text = (
        f"{tx['hi'].format(name=_first_name(order))}\n\n{tx['confirm_intro']}\n\n{table_text}\n\n"
        f"{tx['ship_to']}:\n" + "\n".join(address) + f"\n\n{note}\n\n{tx['view']}\n{link}\n\n{tx['questions']}\n\n{tx['signoff']}"
    )
    html = _shell(
        tx["confirm_subject"].format(number=order.number),
        f"<p>{escape(tx['hi'].format(name=_first_name(order)))}</p><p>{escape(tx['confirm_intro'])}</p>{table_html}"
        f'<p style="margin-top:20px"><strong>{escape(tx["ship_to"])}</strong><br>{"<br>".join(escape(a) for a in address)}</p>'
        f'<p style="white-space:pre-line">{escape(note)}</p>',
        (tx["button"], link), f"{tx['questions']}\n\n{tx['signoff']}",
    )
    await _send(mailer.Mail(to=order.email, subject=tx["confirm_subject"].format(number=order.number), text=text, html=html))


async def order_shipped(order: Order) -> None:
    tx = tr(order.locale)
    details = []
    if order.carrier:
        details.append(f"{tx['carrier']}: {order.carrier}")
    if order.tracking_number:
        details.append(f"{tx['tracking']}: {order.tracking_number}")
    link = order_link(order)
    text = f"{tx['hi'].format(name=_first_name(order))}\n\n{tx['shipped_intro']}\n\n" + "\n".join(details) + f"\n\n{tx['view']}\n{link}\n\n{tx['signoff']}"
    html = _shell(
        tx["shipped_subject"].format(number=order.number),
        f"<p>{escape(tx['hi'].format(name=_first_name(order)))}</p><p>{escape(tx['shipped_intro'])}</p><p>{'<br>'.join(escape(d) for d in details)}</p>",
        (tx["button"], link), tx["signoff"],
    )
    await _send(mailer.Mail(to=order.email, subject=tx["shipped_subject"].format(number=order.number), text=text, html=html))


async def order_refunded(order: Order, amount: Decimal, reason: str | None) -> None:
    tx = tr(order.locale)
    intro = tx["refund_intro"].format(amount=money(amount, order.locale, order.currency))
    extra = f"\n\n{tx['reason']}: {reason}" if reason else ""
    link = order_link(order)
    text = f"{tx['hi'].format(name=_first_name(order))}\n\n{intro}{extra}\n\n{link}\n\n{tx['signoff']}"
    html = _shell(
        tx["refund_subject"].format(number=order.number),
        f"<p>{escape(tx['hi'].format(name=_first_name(order)))}</p><p>{escape(intro)}</p>" + (f"<p>{escape(tx['reason'])}: {escape(reason)}</p>" if reason else ""),
        (tx["button"], link), tx["signoff"],
    )
    await _send(mailer.Mail(to=order.email, subject=tx["refund_subject"].format(number=order.number), text=text, html=html))


async def order_cancelled(order: Order, refunded: bool) -> None:
    tx = tr(order.locale)
    intro = tx["cancel_intro"] + (f" {tx['cancel_refund']}" if refunded else "")
    text = f"{tx['hi'].format(name=_first_name(order))}\n\n{intro}\n\n{tx['questions']}\n\n{tx['signoff']}"
    html = _shell(tx["cancel_subject"].format(number=order.number),
                  f"<p>{escape(tx['hi'].format(name=_first_name(order)))}</p><p>{escape(intro)}</p>", None,
                  f"{tx['questions']}\n\n{tx['signoff']}")
    await _send(mailer.Mail(to=order.email, subject=tx["cancel_subject"].format(number=order.number), text=text, html=html))


async def owner_alert(order: Order, to: str | None, headline: str | None = None) -> None:
    """A short English note to the shop owner."""
    if not to:
        return
    site = get_settings().site_url.rstrip("/")
    lines = [f"{i.quantity} x {i.title}" for i in order.items]
    addr = _address_lines(order.shipping_address)
    subject = headline or f"New order {order.number}: {money(order.grand_total)}"
    text = (
        f"{headline or 'New order ' + order.number}\n\n" + "\n".join(lines)
        + f"\n\nTotal: {money(order.grand_total)} ({order.payment_provider or 'no payment method'})"
        + (f"\nCode used: {order.coupon_code}" if order.coupon_code else "")
        + "\n\nShip to:\n" + "\n".join(addr) + f"\n\nOpen the order: {site}/admin/orders/{order.number}"
    )
    await _send(mailer.Mail(to=to, subject=subject, text=text, reply_to=order.email))


def offer_text(kind: str, value: Decimal, locale: str | None) -> str:
    tx = tr(locale)
    if kind == "percent":
        return tx["offer_percent"].format(value=f"{value:g}")
    if kind == "fixed":
        return tx["offer_fixed"].format(value=money(value, locale))
    return tx["offer_shipping"]


async def coupon_email(*, to: str, code: str, kind: str, value: Decimal, locale: str | None, welcome: bool,
                       expires_at=None, min_subtotal: Decimal | None = None, message: str | None = None) -> None:
    tx = tr(locale)
    offer = offer_text(kind, value, locale)
    intro = (tx["coupon_welcome"] if welcome else tx["coupon_personal"]).format(offer=offer)
    lines = [intro, "", code, ""]
    if min_subtotal:
        lines.append(tx["min_spend"].format(amount=money(min_subtotal, locale)))
    if expires_at:
        lines.append(tx["coupon_valid"].format(date=expires_at.strftime("%Y-%m-%d")))
    lines.append(tx["coupon_use"])
    if message:
        lines += ["", message]
    link = localized(locale, "/shop")
    text = "\n".join(lines) + f"\n\n{link}\n\n{tx['signoff']}"
    html = _shell(
        tx["coupon_subject"],
        f"<p>{escape(intro)}</p><p style=\"font-size:26px;letter-spacing:2px;color:{NAVY};margin:20px 0;font-family:monospace\"><strong>{escape(code)}</strong></p>"
        + "".join(f"<p style=\"color:#555\">{escape(x)}</p>" for x in lines[4:] if x),
        ("WindyCityWares", link), tx["signoff"],
    )
    await _send(mailer.Mail(to=to, subject=tx["coupon_subject"], text=text, html=html))
