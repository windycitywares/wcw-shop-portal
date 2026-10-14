"""Shopper-facing messages from the pricing and checkout code, in English, Spanish and Dutch."""

MESSAGES: dict[str, dict[str, str]] = {
    # coupon problems (domain.pricing.coupon_problem) and outcomes
    "coupon.unknown": {"en": "We don't recognize that code. Check the spelling and try again.",
                       "es": "No reconocemos ese código. Revisa que esté bien escrito e inténtalo de nuevo.",
                       "nl": "We herkennen deze code niet. Controleer de spelling en probeer het opnieuw."},
    "coupon.inactive": {"en": "This code is no longer active.", "es": "Este código ya no está activo.", "nl": "Deze code is niet meer actief."},
    "coupon.not_started": {"en": "This code isn't valid yet.", "es": "Este código todavía no es válido.", "nl": "Deze code is nog niet geldig."},
    "coupon.expired": {"en": "This code has expired.", "es": "Este código ha caducado.", "nl": "Deze code is verlopen."},
    "coupon.used_up": {"en": "This code has been fully redeemed.", "es": "Este código ya se ha canjeado por completo.", "nl": "Deze code is volledig gebruikt."},
    "coupon.wrong_customer": {"en": "This code was issued to a different email address.",
                              "es": "Este código se emitió para otra dirección de correo.",
                              "nl": "Deze code is voor een ander e-mailadres bestemd."},
    "coupon.needs_email": {"en": "Enter your email at checkout and we'll check this code for you.",
                           "es": "Introduce tu correo al pagar y comprobaremos este código.",
                           "nl": "Vul bij het afrekenen je e-mailadres in, dan controleren we deze code."},
    "coupon.per_customer_limit": {"en": "You've already used this code.", "es": "Ya has usado este código.", "nl": "Je hebt deze code al gebruikt."},
    "coupon.first_order_only": {"en": "This code is for first orders only.", "es": "Este código es solo para primeros pedidos.",
                                "nl": "Deze code is alleen voor een eerste bestelling."},
    "coupon.min_subtotal": {"en": "Add items to reach the minimum order for this code.",
                            "es": "Añade artículos para llegar al pedido mínimo de este código.",
                            "nl": "Voeg artikelen toe om het minimumbedrag voor deze code te halen."},
    "coupon.no_eligible_items": {"en": "This code doesn't apply to the items in your cart.",
                                 "es": "Este código no se aplica a los artículos de tu carrito.",
                                 "nl": "Deze code geldt niet voor de artikelen in je winkelwagen."},
    "coupon.better_offer": {"en": "A better offer is already applied to your cart, so this code wasn't needed.",
                            "es": "Ya se aplica una oferta mejor a tu carrito, así que no hizo falta este código.",
                            "nl": "Er is al een betere aanbieding toegepast, dus deze code was niet nodig."},
    # lines
    "line.unavailable": {"en": "{title} is no longer available and was removed.", "es": "{title} ya no está disponible y se quitó.",
                         "nl": "{title} is niet meer beschikbaar en is verwijderd."},
    "line.unavailable_unknown": {"en": "An item in your cart is no longer available and was removed.",
                                 "es": "Un artículo de tu carrito ya no está disponible y se quitó.",
                                 "nl": "Een artikel in je winkelwagen is niet meer beschikbaar en is verwijderd."},
    "line.out_of_stock": {"en": "{title} is out of stock and was removed.", "es": "{title} está agotado y se quitó.",
                          "nl": "{title} is uitverkocht en is verwijderd."},
    "line.reduced": {"en": "Only {n} of {title} left, so we updated your quantity.", "es": "Solo quedan {n} de {title}; actualizamos la cantidad.",
                     "nl": "Er zijn nog maar {n} van {title}; we hebben het aantal aangepast."},
    "line.max": {"en": "You can order up to {n} of {title} at a time.", "es": "Puedes pedir hasta {n} de {title} a la vez.",
                 "nl": "Je kunt maximaal {n} van {title} tegelijk bestellen."},
    "line.choose_option": {"en": "Please choose an option for {title}.", "es": "Elige una opción para {title}.",
                           "nl": "Kies een optie voor {title}."},
    "shipping.undeliverable": {"en": "We don't ship to that country yet.", "es": "Todavía no enviamos a ese país.",
                               "nl": "We verzenden nog niet naar dat land."},
    # checkout
    "checkout.changed": {"en": "Some items in your cart changed. Please review them and try again.",
                         "es": "Algunos artículos de tu carrito cambiaron. Revísalos e inténtalo de nuevo.",
                         "nl": "Er zijn artikelen in je winkelwagen gewijzigd. Controleer ze en probeer het opnieuw."},
    "checkout.empty": {"en": "Your cart is empty.", "es": "Tu carrito está vacío.", "nl": "Je winkelwagen is leeg."},
    "checkout.sold_out": {"en": "Sorry, {title} just sold out.", "es": "Lo sentimos, {title} se acaba de agotar.", "nl": "Sorry, {title} is zojuist uitverkocht."},
    "checkout.code_used_up": {"en": "That code was just fully redeemed.", "es": "Ese código se acaba de canjear por completo.",
                              "nl": "Die code is zojuist volledig gebruikt."},
    "checkout.payment_unavailable": {"en": "That payment method isn't available right now.",
                                     "es": "Ese método de pago no está disponible ahora mismo.",
                                     "nl": "Die betaalmethode is momenteel niet beschikbaar."},
    "checkout.payment_failed": {"en": "We couldn't start the payment. Nothing was charged. Please try again.",
                                "es": "No pudimos iniciar el pago. No se cobró nada. Inténtalo de nuevo.",
                                "nl": "We konden de betaling niet starten. Er is niets afgeschreven. Probeer het opnieuw."},
    "checkout.account_required": {"en": "Please sign in to check out.", "es": "Inicia sesión para pagar.", "nl": "Log in om af te rekenen."},
}


def t(key: str, lang: str | None = "en", **params) -> str:
    entry = MESSAGES.get(key)
    if entry is None:
        return key
    text = entry.get(lang or "en") or entry["en"]
    return text.format(**params) if params else text
