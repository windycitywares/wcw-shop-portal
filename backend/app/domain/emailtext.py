"""Email wording in English, Spanish and Dutch, rendered to plain text and simple HTML.

Customer emails are written warmly and plainly: many shoppers here are buying for a loss, so there are no
countdown timers, no exclamation-mark urgency and no pressure. Everything dynamic is HTML-escaped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from html import escape
from typing import Any

BRAND = "WindyCityWares"
LOCALES = ("en", "es", "nl")

MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    "nl": ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"],
}


def loc(locale: str | None) -> str:
    return locale if locale in LOCALES else "en"


def money(amount: Decimal | float | int, locale: str | None = "en") -> str:
    value = Decimal(str(amount)).quantize(Decimal("0.01"))
    s = f"{abs(value):,.2f}"
    if loc(locale) != "en":
        s = s.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")
    sign = "-" if value < 0 else ""
    return f"{sign}$ {s}" if loc(locale) == "nl" else f"{sign}${s}"


def long_date(moment: date | datetime, locale: str | None = "en") -> str:
    l = loc(locale)
    d = moment.date() if isinstance(moment, datetime) else moment
    month = MONTHS[l][d.month - 1]
    if l == "en":
        return f"{month} {d.day}, {d.year}"
    if l == "es":
        return f"{d.day} de {month} de {d.year}"
    return f"{d.day} {month} {d.year}"


@dataclass
class Rendered:
    subject: str
    text: str
    html: str


# A block is a tuple: ("p", text) | ("button", label, url) | ("rows", [(left, right), ...]) | ("small", text) | ("code", text)
Block = tuple


def _text(blocks: list[Block]) -> str:
    out: list[str] = []
    for b in blocks:
        kind = b[0]
        if kind in ("p", "small"):
            out.append(b[1])
        elif kind == "button":
            out.append(f"{b[1]}: {b[2]}")
        elif kind == "code":
            out.append(f"    {b[1]}")
        elif kind == "rows":
            width = max((len(l) for l, _ in b[1]), default=0)
            out.append("\n".join(f"{l.ljust(width)}  {r}".rstrip() for l, r in b[1]))
    return "\n\n".join(out) + "\n"


def _html(blocks: list[Block], preheader: str) -> str:
    parts: list[str] = []
    for b in blocks:
        kind = b[0]
        if kind == "p":
            parts.append(f'<p style="margin:0 0 16px;line-height:1.55">{escape(b[1]).replace(chr(10), "<br>")}</p>')
        elif kind == "small":
            parts.append(f'<p style="margin:16px 0 0;font-size:12px;line-height:1.5;color:#6b665f">{escape(b[1]).replace(chr(10), "<br>")}</p>')
        elif kind == "code":
            parts.append(
                '<p style="margin:0 0 20px"><span style="display:inline-block;padding:10px 18px;border:1px dashed #8a7f6f;border-radius:8px;'
                f'font:600 20px/1.2 ui-monospace,Menlo,Consolas,monospace;letter-spacing:.08em;background:#faf7f2">{escape(b[1])}</span></p>'
            )
        elif kind == "button":
            parts.append(
                f'<p style="margin:8px 0 22px"><a href="{escape(b[2], quote=True)}" style="display:inline-block;background:#2f3a3f;color:#ffffff;'
                f'text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:600">{escape(b[1])}</a></p>'
            )
        elif kind == "rows":
            rows = "".join(
                f'<tr><td style="padding:6px 12px 6px 0;vertical-align:top">{escape(l)}</td>'
                f'<td style="padding:6px 0;text-align:right;white-space:nowrap;vertical-align:top">{escape(r)}</td></tr>'
                for l, r in b[1]
            )
            parts.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 18px;border-collapse:collapse">{rows}</table>')
    body = "".join(parts)
    return (
        '<!doctype html><html><body style="margin:0;padding:0;background:#f4f1ec;color:#2b2a28;'
        'font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">'
        f'<span style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(preheader)}</span>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:12px">'
        f'<tr><td style="padding:22px 28px 0;font-size:18px;font-weight:700;letter-spacing:.02em">{escape(BRAND)}</td></tr>'
        f'<tr><td style="padding:18px 28px 28px;font-size:15px">{body}</td></tr></table>'
        '</td></tr></table></body></html>'
    )


def _render(subject: str, blocks: list[Block], preheader: str = "") -> Rendered:
    subject = " ".join(subject.split())  # no line breaks in headers
    return Rendered(subject=subject, text=_text(blocks), html=_html(blocks, preheader or subject))


# ---------------------------------------------------------------------------------------------
# Wording. {name} is already "" or " Ana"-style, so greetings read well with and without a name.
# ---------------------------------------------------------------------------------------------
S: dict[str, dict[str, str]] = {
    "hi": {"en": "Hello{name},", "es": "Hola{name}:", "nl": "Hallo{name},"},
    "view_order": {"en": "View your order", "es": "Ver tu pedido", "nl": "Bekijk je bestelling"},
    "order_no": {"en": "Order {number}", "es": "Pedido {number}", "nl": "Bestelling {number}"},
    "subtotal": {"en": "Items", "es": "Artículos", "nl": "Artikelen"},
    "discount": {"en": "Discount", "es": "Descuento", "nl": "Korting"},
    "shipping": {"en": "Shipping", "es": "Envío", "nl": "Verzending"},
    "tax": {"en": "Tax", "es": "Impuestos", "nl": "Belasting"},
    "total": {"en": "Total", "es": "Total", "nl": "Totaal"},
    "free": {"en": "Free", "es": "Gratis", "nl": "Gratis"},
    "ship_to": {"en": "Shipping to:", "es": "Enviar a:", "nl": "Verzenden naar:"},
    "questions": {"en": "Questions? Just reply to this email and a real person will help.",
                  "es": "¿Preguntas? Responde a este correo y una persona real te ayudará.",
                  "nl": "Vragen? Beantwoord deze e-mail en een echt mens helpt je verder."},
    "thanks_sign": {"en": "With care,\nThe WindyCityWares team", "es": "Con cariño,\nEl equipo de WindyCityWares",
                    "nl": "Met zorg,\nHet WindyCityWares-team"},
    "unsub": {"en": "You're receiving this because you asked to hear from us. Unsubscribe: {url}",
              "es": "Recibes este correo porque pediste saber de nosotros. Cancelar suscripción: {url}",
              "nl": "Je ontvangt dit omdat je van ons wilt horen. Uitschrijven: {url}"},
}


def s(key: str, locale: str | None, **kw: Any) -> str:
    entry = S[key]
    text = entry.get(loc(locale)) or entry["en"]
    return text.format(**kw) if kw else text


def _greet(ctx: dict[str, Any]) -> str:
    name = (ctx.get("name") or "").strip().split(" ")[0] if ctx.get("name") else ""
    return s("hi", ctx.get("locale"), name=f" {name}" if name else "")


def _items_rows(ctx: dict[str, Any]) -> list[tuple[str, str]]:
    return [(f"{i['title']} × {i['qty']}" if i["qty"] > 1 else i["title"], i.get("total", "")) for i in ctx.get("items", [])]


def _totals_rows(ctx: dict[str, Any]) -> list[tuple[str, str]]:
    l = ctx.get("locale")
    rows = [(s("subtotal", l), ctx["subtotal"])]
    if ctx.get("discount"):
        rows.append((s("discount", l), "−" + ctx["discount"]))
    rows.append((s("shipping", l), ctx["shipping"] if ctx.get("shipping") else s("free", l)))
    if ctx.get("tax"):
        rows.append((s("tax", l), ctx["tax"]))
    rows.append((s("total", l), ctx["total"]))
    return rows


def _unsub(ctx: dict[str, Any]) -> list[Block]:
    return [("small", s("unsub", ctx.get("locale"), url=ctx["unsubscribe_url"]))] if ctx.get("unsubscribe_url") else []


T: dict[str, dict[str, Any]] = {}


def _order_received(ctx: dict[str, Any]) -> Rendered:
    """Order placed but not paid yet (pay-later): what we received and how to pay."""
    l = loc(ctx.get("locale"))
    subject = {"en": "We received your order {number}", "es": "Recibimos tu pedido {number}", "nl": "We hebben je bestelling {number} ontvangen"}[l].format(**ctx)
    intro = {"en": "Thank you. We've received your order and are holding it for you. It will be prepared as soon as payment is confirmed.",
             "es": "Gracias. Recibimos tu pedido y lo estamos reservando. Lo prepararemos en cuanto se confirme el pago.",
             "nl": "Dank je wel. We hebben je bestelling ontvangen en houden die voor je vast. We maken hem klaar zodra de betaling is bevestigd."}[l]
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro)]
    if ctx.get("instructions"):
        blocks.append(("p", {"en": "How to pay:", "es": "Cómo pagar:", "nl": "Zo betaal je:"}[l]))
        blocks.append(("p", ctx["instructions"]))
    blocks += [("rows", _items_rows(ctx)), ("rows", _totals_rows(ctx))]
    if ctx.get("address"):
        blocks.append(("p", s("ship_to", l) + "\n" + ctx["address"]))
    blocks += [("button", s("view_order", l), ctx["link"]), ("p", s("questions", l)), ("p", s("thanks_sign", l))]
    return _render(subject, blocks)


def _order_confirmation(ctx: dict[str, Any]) -> Rendered:
    l = loc(ctx.get("locale"))
    subject = {"en": "Your order {number} is confirmed", "es": "Tu pedido {number} está confirmado", "nl": "Je bestelling {number} is bevestigd"}[l].format(**ctx)
    intro = {"en": "Thank you for your order. Your payment was received and we're getting everything ready. We'll email you again when it ships.",
             "es": "Gracias por tu pedido. Recibimos tu pago y estamos preparando todo. Te escribiremos de nuevo cuando salga el envío.",
             "nl": "Dank je wel voor je bestelling. We hebben je betaling ontvangen en maken alles klaar. Zodra hij onderweg is, mailen we je opnieuw."}[l]
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro), ("rows", _items_rows(ctx)), ("rows", _totals_rows(ctx))]
    if ctx.get("address"):
        blocks.append(("p", s("ship_to", l) + "\n" + ctx["address"]))
    if ctx.get("delivery_estimate"):
        blocks.append(("p", {"en": "Estimated delivery: {d}", "es": "Entrega estimada: {d}", "nl": "Verwachte levering: {d}"}[l].format(d=ctx["delivery_estimate"])))
    blocks += [("button", s("view_order", l), ctx["link"]), ("p", s("questions", l)), ("p", s("thanks_sign", l))]
    return _render(subject, blocks)


def _order_shipped(ctx: dict[str, Any]) -> Rendered:
    l = loc(ctx.get("locale"))
    subject = {"en": "Your order {number} is on its way", "es": "Tu pedido {number} va en camino", "nl": "Je bestelling {number} is onderweg"}[l].format(**ctx)
    intro = {"en": "Good news: your order has shipped.", "es": "Buenas noticias: tu pedido ya salió.", "nl": "Goed nieuws: je bestelling is verzonden."}[l]
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro)]
    rows = []
    if ctx.get("carrier"):
        rows.append(({"en": "Carrier", "es": "Transportista", "nl": "Vervoerder"}[l], ctx["carrier"]))
    if ctx.get("tracking_number"):
        rows.append(({"en": "Tracking number", "es": "Número de seguimiento", "nl": "Trackingnummer"}[l], ctx["tracking_number"]))
    if rows:
        blocks.append(("rows", rows))
    if ctx.get("tracking_url"):
        blocks.append(("button", {"en": "Track your package", "es": "Seguir tu paquete", "nl": "Volg je pakket"}[l], ctx["tracking_url"]))
    blocks += [("button", s("view_order", l), ctx["link"]), ("p", s("questions", l)), ("p", s("thanks_sign", l))]
    return _render(subject, blocks)


def _order_cancelled(ctx: dict[str, Any]) -> Rendered:
    l = loc(ctx.get("locale"))
    subject = {"en": "Your order {number} was cancelled", "es": "Tu pedido {number} fue cancelado", "nl": "Je bestelling {number} is geannuleerd"}[l].format(**ctx)
    intro = {"en": "Your order has been cancelled.", "es": "Tu pedido ha sido cancelado.", "nl": "Je bestelling is geannuleerd."}[l]
    refund = {"en": "If you had already paid, the refund is on its way and usually appears within 5-10 business days.",
              "es": "Si ya habías pagado, el reembolso está en camino y suele verse en 5-10 días hábiles.",
              "nl": "Als je al had betaald, is de terugbetaling onderweg en staat die meestal binnen 5-10 werkdagen op je rekening."}[l]
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro)]
    if ctx.get("refund_note", True):
        blocks.append(("p", refund))
    blocks += [("button", s("view_order", l), ctx["link"]), ("p", s("questions", l)), ("p", s("thanks_sign", l))]
    return _render(subject, blocks)


def _order_refunded(ctx: dict[str, Any]) -> Rendered:
    l = loc(ctx.get("locale"))
    subject = {"en": "Refund for order {number}", "es": "Reembolso del pedido {number}", "nl": "Terugbetaling voor bestelling {number}"}[l].format(**ctx)
    intro = {"en": "We've refunded {amount} to your original payment method. It usually appears within 5-10 business days.",
             "es": "Hemos reembolsado {amount} a tu método de pago original. Suele verse en 5-10 días hábiles.",
             "nl": "We hebben {amount} teruggestort op je oorspronkelijke betaalmethode. Dat staat er meestal binnen 5-10 werkdagen."}[l].format(**ctx)
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro), ("button", s("view_order", l), ctx["link"]), ("p", s("questions", l)), ("p", s("thanks_sign", l))]
    return _render(subject, blocks)


def _welcome_offer(ctx: dict[str, Any]) -> Rendered:
    l = loc(ctx.get("locale"))
    subject = {"en": "Welcome to WindyCityWares: your {percent}% welcome offer", "es": "Bienvenido a WindyCityWares: tu oferta de bienvenida del {percent}%",
               "nl": "Welkom bij WindyCityWares: je welkomstkorting van {percent}%"}[l].format(**ctx)
    intro = {"en": "Thank you for joining us. Here is a welcome code for {percent}% off your first order, valid until {expires}.",
             "es": "Gracias por unirte. Aquí tienes un código de bienvenida con un {percent}% de descuento en tu primer pedido, válido hasta el {expires}.",
             "nl": "Fijn dat je erbij bent. Hier is je welkomstcode voor {percent}% korting op je eerste bestelling, geldig tot {expires}."}[l].format(**ctx)
    how = {"en": "Enter the code at checkout. It is yours alone. Take your time: there's no rush.",
           "es": "Introduce el código al pagar. Es solo tuyo. Sin prisa: tómate el tiempo que necesites.",
           "nl": "Vul de code in bij het afrekenen. Hij is alleen voor jou. Neem rustig de tijd."}[l]
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro), ("code", ctx["code"]), ("p", how),
                           ("button", {"en": "Browse the shop", "es": "Ver la tienda", "nl": "Bekijk de winkel"}[l], ctx["shop_url"]),
                           ("p", s("thanks_sign", l)), *_unsub(ctx)]
    return _render(subject, blocks)


def _account_welcome(ctx: dict[str, Any]) -> Rendered:
    """The hello that follows a new account. Not marketing: the address did not opt in, so no unsubscribe footer."""
    l = loc(ctx.get("locale"))
    subject = {"en": "Welcome to WindyCityWares", "es": "Bienvenido a WindyCityWares",
               "nl": "Welkom bij WindyCityWares"}[l]
    intro = {
        "en": "Your account is ready. Keep the designs you love in your wishlist, follow your orders, and check out faster next time.",
        "es": "Tu cuenta está lista. Guarda los diseños que te gustan en tu lista de deseos, sigue tus pedidos y paga más rápido la próxima vez.",
        "nl": "Je account is klaar. Bewaar de ontwerpen die je mooi vindt op je verlanglijst, volg je bestellingen en reken de volgende keer sneller af.",
    }[l]
    forgot = {
        "en": "If you ever forget your password, use \"Forgot password\" on the sign-in page and we'll email you a link to set a new one.",
        "es": "Si alguna vez olvidas tu contraseña, usa \"Olvidé mi contraseña\" en la página de inicio de sesión y te enviaremos un enlace para crear una nueva.",
        "nl": "Als je je wachtwoord vergeet, gebruik dan \"Wachtwoord vergeten\" op de inlogpagina. We sturen je dan een link om een nieuw wachtwoord in te stellen.",
    }[l]
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro),
                           ("button", {"en": "Visit your account", "es": "Ver tu cuenta", "nl": "Naar je account"}[l], ctx["account_url"]),
                           ("p", forgot), ("p", s("questions", l)), ("p", s("thanks_sign", l))]
    return _render(subject, blocks)


def _password_reset(ctx: dict[str, Any]) -> Rendered:
    """The one-time reset link. Short and to the point: the link is the whole message."""
    l = loc(ctx.get("locale"))
    subject = {"en": "Reset your WindyCityWares password", "es": "Restablece tu contraseña de WindyCityWares",
               "nl": "Stel je WindyCityWares-wachtwoord opnieuw in"}[l]
    intro = {
        "en": "Someone asked to reset the password for this address. Set a new one with the button below.",
        "es": "Alguien pidió restablecer la contraseña de esta dirección. Crea una nueva con el botón de abajo.",
        "nl": "Iemand vroeg om het wachtwoord van dit adres opnieuw in te stellen. Stel hieronder een nieuw wachtwoord in.",
    }[l]
    note = {
        "en": "The link works once and expires in {minutes} minutes. If it wasn't you, you can ignore this email: nothing has changed.",
        "es": "El enlace funciona una sola vez y caduca en {minutes} minutos. Si no fuiste tú, puedes ignorar este correo: nada ha cambiado.",
        "nl": "De link werkt één keer en verloopt na {minutes} minuten. Was jij dit niet? Dan kun je deze e-mail negeren: er is niets veranderd.",
    }[l].format(minutes=ctx["minutes"])
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro),
                           ("button", {"en": "Set a new password", "es": "Crear una contraseña nueva",
                                       "nl": "Nieuw wachtwoord instellen"}[l], ctx["link"]),
                           ("p", note), ("p", s("thanks_sign", l))]
    return _render(subject, blocks)


def _abandoned_cart(ctx: dict[str, Any]) -> Rendered:
    l = loc(ctx.get("locale"))
    second = ctx.get("step", 1) >= 2
    subject = {"en": "Your cart is saved", "es": "Tu carrito está guardado", "nl": "Je winkelwagen is bewaard"}[l]
    intro = {"en": "You left a few things in your cart. They're saved, so you can come back whenever you're ready.",
             "es": "Dejaste algunos artículos en tu carrito. Están guardados, así que puedes volver cuando quieras.",
             "nl": "Je hebt een paar dingen in je winkelwagen laten staan. Ze zijn bewaard, dus je kunt terugkomen wanneer je er klaar voor bent."}[l]
    if second:
        intro = {"en": "Just a gentle note that your cart is still saved. If you have any questions about sizes, materials or shipping, we're glad to help.",
                 "es": "Solo un recordatorio amable: tu carrito sigue guardado. Si tienes dudas sobre tamaños, materiales o envíos, con gusto te ayudamos.",
                 "nl": "Een vriendelijke herinnering dat je winkelwagen nog bewaard is. Heb je vragen over maten, materialen of verzending? We helpen je graag."}[l]
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro), ("rows", [(f"{i['title']} × {i['qty']}" if i["qty"] > 1 else i["title"], "") for i in ctx.get("items", [])])]
    if ctx.get("code"):
        offer = {"en": "As a small thank-you, here is {percent}% off if you decide to order:", "es": "Como pequeño agradecimiento, aquí tienes un {percent}% de descuento si decides pedir:",
                 "nl": "Als klein bedankje: {percent}% korting als je besluit te bestellen:"}[l].format(percent=ctx.get("percent", ""))
        blocks += [("p", offer), ("code", ctx["code"])]
    blocks += [("button", {"en": "Return to your cart", "es": "Volver a tu carrito", "nl": "Terug naar je winkelwagen"}[l], ctx["link"]),
               ("p", s("questions", l)), ("p", s("thanks_sign", l)), *_unsub(ctx)]
    return _render(subject, blocks)


def _review_request(ctx: dict[str, Any]) -> Rendered:
    l = loc(ctx.get("locale"))
    subject = {"en": "How is everything?", "es": "¿Cómo va todo?", "nl": "Hoe gaat het?"}[l]
    intro = {"en": "We hope your order arrived safely. When you have a moment, a few words about it help other families choose with confidence. Only if you feel like it.",
             "es": "Esperamos que tu pedido haya llegado bien. Cuando tengas un momento, unas palabras sobre él ayudan a otras familias a elegir con confianza. Solo si te apetece.",
             "nl": "We hopen dat je bestelling goed is aangekomen. Als je een moment hebt, helpen een paar woorden andere gezinnen om met vertrouwen te kiezen. Alleen als je zin hebt."}[l]
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro)]
    for item in ctx.get("items", []):
        blocks.append(("button", {"en": "Review {t}", "es": "Opinar sobre {t}", "nl": "Beoordeel {t}"}[l].format(t=item["title"]), item["url"]))
    blocks += [("p", s("thanks_sign", l)), *_unsub(ctx)]
    return _render(subject, blocks)


def _back_in_stock(ctx: dict[str, Any]) -> Rendered:
    l = loc(ctx.get("locale"))
    subject = {"en": "{title} is back in stock", "es": "{title} vuelve a estar disponible", "nl": "{title} is weer op voorraad"}[l].format(**ctx)
    intro = {"en": "You asked us to let you know: {title} is available again. Stock is limited.",
             "es": "Nos pediste que te avisáramos: {title} vuelve a estar disponible. Las existencias son limitadas.",
             "nl": "Je vroeg ons je te waarschuwen: {title} is weer beschikbaar. De voorraad is beperkt."}[l].format(**ctx)
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro), ("button", {"en": "View the product", "es": "Ver el producto", "nl": "Bekijk het product"}[l], ctx["link"]),
                           ("p", s("thanks_sign", l))]
    return _render(subject, blocks)


def _request_available(ctx: dict[str, Any]) -> Rendered:
    """Staff answering a stock request: it can be ordered now (with an optional personal line from the shop)."""
    l = loc(ctx.get("locale"))
    subject = {"en": "Good news: {title} is available", "es": "Buenas noticias: {title} está disponible",
               "nl": "Goed nieuws: {title} is beschikbaar"}[l].format(**ctx)
    intro = {"en": "You asked us about {title}. It can be ordered now.",
             "es": "Nos preguntaste por {title}. Ya se puede pedir.",
             "nl": "Je vroeg ons naar {title}. Je kunt het nu bestellen."}[l].format(**ctx)
    blocks: list[Block] = [("p", _greet(ctx)), ("p", intro)]
    if ctx.get("message"):
        blocks.append(("p", str(ctx["message"])))
    blocks += [("button", {"en": "View the product", "es": "Ver el producto", "nl": "Bekijk het product"}[l], ctx["link"]), ("p", s("thanks_sign", l))]
    return _render(subject, blocks)


def _campaign(ctx: dict[str, Any]) -> Rendered:
    l = loc(ctx.get("locale"))
    blocks: list[Block] = [("p", _greet(ctx))]
    for para in [p.strip() for p in str(ctx["body"]).split("\n\n") if p.strip()]:
        blocks.append(("p", para))
    if ctx.get("code"):
        blocks.append(("code", ctx["code"]))
        if ctx.get("expires"):
            blocks.append(("small", {"en": "Valid until {d}.", "es": "Válido hasta el {d}.", "nl": "Geldig tot {d}."}[l].format(d=ctx["expires"])))
    if ctx.get("shop_url"):
        blocks.append(("button", {"en": "Browse the shop", "es": "Ver la tienda", "nl": "Bekijk de winkel"}[l], ctx["shop_url"]))
    blocks += [("p", s("thanks_sign", l)), *_unsub(ctx)]
    return _render(ctx["subject"], blocks)


def _admin_new_order(ctx: dict[str, Any]) -> Rendered:
    blocks: list[Block] = [("p", f"New order {ctx['number']} from {ctx['customer']}"), ("rows", _items_rows(ctx)),
                           ("rows", [("Total", ctx["total"]), ("Payment", ctx["payment"])]), ("button", "Open the order", ctx["link"])]
    return _render(f"New order {ctx['number']} ({ctx['total']})", blocks)


def _digest(ctx: dict[str, Any]) -> Rendered:
    blocks: list[Block] = [("p", ctx["intro"]), ("rows", ctx["kpis"])]
    for title, lines in ctx.get("sections", []):
        blocks.append(("p", title))
        blocks.append(("rows", [(x, "") for x in lines]))
    blocks.append(("button", "Open the dashboard", ctx["link"]))
    return _render(ctx["subject"], blocks)


RENDERERS = {
    "order_received": _order_received,
    "order_confirmation": _order_confirmation,
    "order_shipped": _order_shipped,
    "order_cancelled": _order_cancelled,
    "order_refunded": _order_refunded,
    "welcome_offer": _welcome_offer,
    "account_welcome": _account_welcome,
    "password_reset": _password_reset,
    "abandoned_cart": _abandoned_cart,
    "review_request": _review_request,
    "back_in_stock": _back_in_stock,
    "request_available": _request_available,
    "campaign": _campaign,
    "admin_new_order": _admin_new_order,
    "digest": _digest,
}


def render(kind: str, ctx: dict[str, Any]) -> Rendered:
    return RENDERERS[kind](ctx)
