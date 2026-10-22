/**
 * Help and policy pages (/help/<topic>) in English, Spanish and Dutch.
 *
 * Placeholders filled from Admin → Settings at request time: {flat} flat shipping rate, {free} free-shipping
 * threshold, {handling} days to prepare, {transit} days in transit, {total} total delivery days, {email} shop email.
 * The returns, privacy and terms texts are sensible starting drafts: the owner should review them (and have the
 * legal pages checked) before launch.
 */

export const HELP_TOPICS = ["faq", "shipping", "returns", "privacy", "terms"] as const;
export type HelpTopic = (typeof HELP_TOPICS)[number];

export interface HelpSection {
  heading: string;
  paragraphs?: string[];
  bullets?: string[];
}

export interface HelpPage {
  title: string;
  description: string;
  sections: HelpSection[];
}

type Lang = "en" | "es" | "nl";

export const HELP_NAV: Record<Lang, Record<HelpTopic, string>> = {
  en: { faq: "FAQ", shipping: "Shipping", returns: "Returns", privacy: "Privacy", terms: "Terms" },
  es: { faq: "Preguntas frecuentes", shipping: "Envíos", returns: "Devoluciones", privacy: "Privacidad", terms: "Condiciones" },
  nl: { faq: "Veelgestelde vragen", shipping: "Verzending", returns: "Retourneren", privacy: "Privacy", terms: "Voorwaarden" },
};

export const HELP: Record<Lang, Record<HelpTopic, HelpPage>> = {
  en: {
    faq: {
      title: "Frequently asked questions",
      description: "Sizes, materials, shipping, payment and orders: answers to the questions shoppers ask us most.",
      sections: [
        { heading: "How do I choose the right size?", paragraphs: ["Each product page lists the dimensions of the item, and often a photo for scale. Measure the space you have in mind and compare. If you're unsure, contact us and we'll help you choose."] },
        { heading: "Can I add engraving or a personal note?", paragraphs: ["Leave a note at checkout with what you'd like, or contact us before ordering. We'll confirm the details with you by email before preparing your order."] },
        { heading: "How long does delivery take?", paragraphs: ["Most orders are prepared in {handling} business days and arrive {transit} business days after shipping. You'll receive an email with tracking as soon as your order ships."] },
        { heading: "How can I pay?", paragraphs: ["You pay by card on Stripe's secure payment page. We never see or store your card number. If you would rather pay another way, contact us before ordering and we will find something that works."] },
        { heading: "Where is my order?", paragraphs: ["Use the link in your order confirmation email, or go to Find my order and enter your order number and email address. If you have an account, your orders are listed there too."] },
        { heading: "Do you ship outside the United States?", paragraphs: ["For now we ship within the United States. If you need delivery elsewhere, contact us and we'll see what we can do."] },
        { heading: "Can I use more than one discount code?", paragraphs: ["Usually one code per order. Automatic offers and sale prices are applied for you, and the cart always shows the best price."] },
      ],
    },
    shipping: {
      title: "Shipping",
      description: "Shipping costs, delivery times and tracking for orders from Windy City Wares.",
      sections: [
        { heading: "Costs", bullets: ["Standard shipping: {flat} per order.", "Free shipping on orders of {free} or more (after discounts).", "The cart shows how much more you need for free shipping."] },
        { heading: "Delivery times", paragraphs: ["We prepare orders in {handling} business days. Delivery then takes {transit} business days, so most orders arrive within {total} business days of ordering."] },
        { heading: "Tracking", paragraphs: ["As soon as your order ships we email you the carrier and tracking number. Your private order page shows the progress at any time."] },
        { heading: "Something wrong with your delivery?", paragraphs: ["If a parcel arrives damaged, keep the packaging, take a photo and contact us within 7 days. We'll make it right."] },
      ],
    },
    returns: {
      title: "Returns and refunds",
      description: "How returns, exchanges and refunds work at Windy City Wares.",
      sections: [
        { heading: "Returns", paragraphs: ["You can return unused items in their original packaging within 30 days of delivery. Contact us first with your order number so we can help and share the return address."] },
        { heading: "Items we can't take back", bullets: ["Engraved or personalized items, unless they arrived damaged or not as described.", "Items that have been used or damaged after delivery."] },
        { heading: "Refunds", paragraphs: ["Once we receive the return we refund the item price to your original payment method, usually within 5 to 10 business days. You'll get an email when the refund is made."] },
        { heading: "Damaged or wrong items", paragraphs: ["If something arrives damaged or isn't what you ordered, contact us within 7 days with a photo. We'll replace it or refund it in full, including shipping."] },
      ],
    },
    privacy: {
      title: "Privacy policy",
      description: "What information Windy City Wares collects, why, and the choices you have.",
      sections: [
        { heading: "What we collect", bullets: ["Your order: name, email, phone (optional), shipping address and what you bought, so we can deliver it and send order emails.", "Your account, if you create one: email, name, saved addresses and wishlist.", "Your card details are entered on Stripe's page and never reach us."] },
        { heading: "Visit statistics (only with your permission)", paragraphs: ["If you accept in the banner, we count visits and what people look at to improve the shop: pages viewed, searches, cart activity and page speed. We don't use advertising trackers, we don't follow you across other sites, and we don't store IP addresses. Search terms that look like an email address or phone number are discarded. Statistics are deleted after the retention period set in our settings. You can change your choice any time with Analytics choices at the bottom of every page."] },
        { heading: "Emails", paragraphs: ["We send emails about your orders. News and offers only if you ask for them, and every one has an unsubscribe link. Cart reminders only if you ask for them at checkout."] },
        { heading: "Who we share it with", bullets: ["Stripe, to take card payments.", "Our email and hosting providers, to send emails and run the shop.", "Carriers, to deliver your order.", "We never sell your information."] },
        { heading: "Your choices", paragraphs: ["Contact us to see, correct or delete your information. You can unsubscribe from marketing emails with the link in any of them."] },
      ],
    },
    terms: {
      title: "Terms of sale",
      description: "The terms that apply when you order from Windy City Wares.",
      sections: [
        { heading: "Orders", paragraphs: ["Your order is confirmed when we've received payment and emailed your confirmation. If an item becomes unavailable we'll tell you and refund it."] },
        { heading: "Prices", paragraphs: ["Prices are in US dollars. Sale prices and offers apply while they run; the price shown at checkout is the price you pay. Sales tax is added where required."] },
        { heading: "Shipping and returns", paragraphs: ["See our Shipping and Returns pages."] },
        { heading: "Contact", paragraphs: ["Questions about an order? Use the contact page and we'll reply by email, usually within one business day."] },
      ],
    },
  },
  es: {
    faq: {
      title: "Preguntas frecuentes",
      description: "Tamaños, materiales, envíos, pagos y pedidos: respuestas a las preguntas más habituales.",
      sections: [
        { heading: "¿Cómo elijo el tamaño adecuado?", paragraphs: ["Cada página de producto indica las dimensiones del artículo y, a menudo, una foto para tener una referencia de escala. Mide el espacio que tienes pensado y compara. Si tienes dudas, contáctanos y te ayudamos a elegir."] },
        { heading: "¿Puedo añadir un grabado o una nota personal?", paragraphs: ["Deja una nota al pagar con lo que deseas, o escríbenos antes de hacer el pedido. Te confirmaremos los detalles por email antes de prepararlo."] },
        { heading: "¿Cuánto tarda la entrega?", paragraphs: ["La mayoría de los pedidos se preparan en {handling} días hábiles y llegan {transit} días hábiles después del envío. Recibirás un email con el seguimiento en cuanto salga tu pedido."] },
        { heading: "¿Cómo puedo pagar?", paragraphs: ["Pagas con tarjeta en la página segura de Stripe. Nunca vemos ni guardamos el número de tu tarjeta. Si prefieres pagar de otra forma, escríbenos antes de hacer el pedido y buscamos una solución."] },
        { heading: "¿Dónde está mi pedido?", paragraphs: ["Usa el enlace del email de confirmación o ve a Buscar mi pedido e introduce el número de pedido y tu email. Si tienes cuenta, tus pedidos también aparecen allí."] },
        { heading: "¿Envían fuera de Estados Unidos?", paragraphs: ["Por ahora enviamos dentro de Estados Unidos. Si necesitas entrega en otro lugar, escríbenos y veremos qué podemos hacer."] },
        { heading: "¿Puedo usar más de un código de descuento?", paragraphs: ["Normalmente un código por pedido. Las ofertas automáticas y los precios rebajados se aplican solos, y el carrito siempre muestra el mejor precio."] },
      ],
    },
    shipping: {
      title: "Envíos",
      description: "Costes de envío, plazos de entrega y seguimiento de los pedidos de Windy City Wares.",
      sections: [
        { heading: "Costes", bullets: ["Envío estándar: {flat} por pedido.", "Envío gratis en pedidos de {free} o más (después de descuentos).", "El carrito muestra cuánto falta para el envío gratis."] },
        { heading: "Plazos de entrega", paragraphs: ["Preparamos los pedidos en {handling} días hábiles. La entrega tarda después {transit} días hábiles, así que la mayoría llega en {total} días hábiles desde el pedido."] },
        { heading: "Seguimiento", paragraphs: ["En cuanto sale tu pedido te enviamos por email el transportista y el número de seguimiento. Tu página privada del pedido muestra el progreso en todo momento."] },
        { heading: "¿Algún problema con la entrega?", paragraphs: ["Si un paquete llega dañado, guarda el embalaje, haz una foto y escríbenos en un plazo de 7 días. Lo solucionaremos."] },
      ],
    },
    returns: {
      title: "Devoluciones y reembolsos",
      description: "Cómo funcionan las devoluciones, cambios y reembolsos en Windy City Wares.",
      sections: [
        { heading: "Devoluciones", paragraphs: ["Puedes devolver artículos sin usar en su embalaje original en los 30 días siguientes a la entrega. Escríbenos primero con tu número de pedido para ayudarte y darte la dirección de devolución."] },
        { heading: "Artículos que no podemos aceptar", bullets: ["Artículos grabados o personalizados, salvo que lleguen dañados o no coincidan con la descripción.", "Artículos que se hayan usado o dañado después de la entrega."] },
        { heading: "Reembolsos", paragraphs: ["Cuando recibimos la devolución, reembolsamos el precio del artículo al método de pago original, normalmente en 5 a 10 días hábiles. Recibirás un email cuando se haga el reembolso."] },
        { heading: "Artículos dañados o equivocados", paragraphs: ["Si algo llega dañado o no es lo que pediste, escríbenos en 7 días con una foto. Lo cambiaremos o te devolveremos el importe completo, envío incluido."] },
      ],
    },
    privacy: {
      title: "Política de privacidad",
      description: "Qué información recoge Windy City Wares, para qué y qué opciones tienes.",
      sections: [
        { heading: "Qué recogemos", bullets: ["Tu pedido: nombre, email, teléfono (opcional), dirección de envío y lo que compraste, para entregarlo y enviarte los emails del pedido.", "Tu cuenta, si creas una: email, nombre, direcciones guardadas y favoritos.", "Los datos de tu tarjeta se introducen en la página de Stripe y nunca nos llegan."] },
        { heading: "Estadísticas de visitas (solo con tu permiso)", paragraphs: ["Si aceptas en el aviso, contamos las visitas y lo que se mira para mejorar la tienda: páginas vistas, búsquedas, actividad del carrito y velocidad de la página. No usamos rastreadores publicitarios, no te seguimos en otros sitios y no guardamos direcciones IP. Las búsquedas que parecen un email o un teléfono se descartan. Las estadísticas se borran tras el periodo de conservación fijado en nuestra configuración. Puedes cambiar tu elección cuando quieras con Opciones de analítica, al pie de cada página."] },
        { heading: "Emails", paragraphs: ["Te enviamos emails sobre tus pedidos. Novedades y ofertas solo si las pides, y todas incluyen un enlace para darte de baja. Recordatorios del carrito solo si los pides al pagar."] },
        { heading: "Con quién la compartimos", bullets: ["Stripe, para cobrar con tarjeta.", "Nuestros proveedores de email y alojamiento, para enviar emails y mantener la tienda.", "Los transportistas, para entregar tu pedido.", "Nunca vendemos tu información."] },
        { heading: "Tus opciones", paragraphs: ["Escríbenos para ver, corregir o borrar tu información. Puedes darte de baja de los emails comerciales con el enlace que incluye cada uno."] },
      ],
    },
    terms: {
      title: "Condiciones de venta",
      description: "Las condiciones que se aplican cuando haces un pedido en Windy City Wares.",
      sections: [
        { heading: "Pedidos", paragraphs: ["Tu pedido queda confirmado cuando recibimos el pago y te enviamos la confirmación por email. Si un artículo deja de estar disponible te avisaremos y te lo reembolsaremos."] },
        { heading: "Precios", paragraphs: ["Los precios están en dólares estadounidenses. Las rebajas y ofertas se aplican mientras estén vigentes; el precio que ves al pagar es el que pagas. Se añade el impuesto sobre las ventas donde corresponda."] },
        { heading: "Envíos y devoluciones", paragraphs: ["Consulta nuestras páginas de Envíos y Devoluciones."] },
        { heading: "Contacto", paragraphs: ["¿Preguntas sobre un pedido? Usa la página de contacto y te responderemos por email, normalmente en un día hábil."] },
      ],
    },
  },
  nl: {
    faq: {
      title: "Veelgestelde vragen",
      description: "Maten, materialen, verzending, betalen en bestellingen: antwoorden op de vragen die klanten ons het vaakst stellen.",
      sections: [
        { heading: "Hoe kies ik de juiste maat?", paragraphs: ["Op elke productpagina staan de afmetingen van het artikel, vaak met een foto ter vergelijking. Meet de ruimte die je in gedachten hebt en vergelijk. Twijfel je, neem dan contact op en we helpen je kiezen."] },
        { heading: "Kan ik een gravure of persoonlijke boodschap toevoegen?", paragraphs: ["Laat bij het afrekenen een opmerking achter met je wensen, of neem vóór het bestellen contact op. We bevestigen de details per e-mail voordat we je bestelling klaarmaken."] },
        { heading: "Hoe lang duurt de levering?", paragraphs: ["De meeste bestellingen maken we in {handling} werkdagen klaar en ze komen {transit} werkdagen na verzending aan. Zodra je bestelling onderweg is, krijg je een e-mail met de tracking."] },
        { heading: "Hoe kan ik betalen?", paragraphs: ["Je betaalt met je kaart op de beveiligde betaalpagina van Stripe. Wij zien of bewaren je kaartnummer nooit. Liever op een andere manier betalen? Neem dan contact op vóór je bestelt, dan zoeken we een oplossing."] },
        { heading: "Waar is mijn bestelling?", paragraphs: ["Gebruik de link in je bevestigingsmail, of ga naar Mijn bestelling zoeken en vul je bestelnummer en e-mailadres in. Heb je een account, dan staan je bestellingen daar ook."] },
        { heading: "Verzenden jullie buiten de Verenigde Staten?", paragraphs: ["Voorlopig verzenden we binnen de Verenigde Staten. Heb je levering elders nodig, neem dan contact op en we kijken wat er mogelijk is."] },
        { heading: "Kan ik meer dan één kortingscode gebruiken?", paragraphs: ["Meestal één code per bestelling. Automatische aanbiedingen en kortingsprijzen worden vanzelf toegepast, en de winkelwagen toont altijd de beste prijs."] },
      ],
    },
    shipping: {
      title: "Verzending",
      description: "Verzendkosten, levertijden en tracking voor bestellingen bij Windy City Wares.",
      sections: [
        { heading: "Kosten", bullets: ["Standaardverzending: {flat} per bestelling.", "Gratis verzending vanaf {free} (na korting).", "De winkelwagen laat zien hoeveel je nog nodig hebt voor gratis verzending."] },
        { heading: "Levertijden", paragraphs: ["We maken bestellingen in {handling} werkdagen klaar. De levering duurt daarna {transit} werkdagen, dus de meeste bestellingen zijn binnen {total} werkdagen na het bestellen bij je."] },
        { heading: "Tracking", paragraphs: ["Zodra je bestelling verzonden is, mailen we je de vervoerder en het trackingnummer. Op je privé-bestelpagina zie je altijd de voortgang."] },
        { heading: "Iets mis met je levering?", paragraphs: ["Komt een pakket beschadigd aan, bewaar dan de verpakking, maak een foto en neem binnen 7 dagen contact op. We lossen het op."] },
      ],
    },
    returns: {
      title: "Retourneren en terugbetalen",
      description: "Hoe retouren, ruilen en terugbetalingen werken bij Windy City Wares.",
      sections: [
        { heading: "Retourneren", paragraphs: ["Ongebruikte artikelen in de originele verpakking kun je binnen 30 dagen na levering retourneren. Neem eerst contact op met je bestelnummer, dan helpen we je en sturen we het retouradres."] },
        { heading: "Artikelen die we niet terugnemen", bullets: ["Gegraveerde of gepersonaliseerde artikelen, tenzij ze beschadigd of anders dan beschreven aankwamen.", "Artikelen die gebruikt of na levering beschadigd zijn."] },
        { heading: "Terugbetaling", paragraphs: ["Zodra we de retour ontvangen, betalen we de prijs van het artikel terug via je oorspronkelijke betaalmethode, meestal binnen 5 tot 10 werkdagen. Je krijgt een e-mail zodra dat gebeurd is."] },
        { heading: "Beschadigde of verkeerde artikelen", paragraphs: ["Komt iets beschadigd aan of is het niet wat je bestelde, neem dan binnen 7 dagen contact op met een foto. We vervangen het of betalen alles terug, inclusief verzending."] },
      ],
    },
    privacy: {
      title: "Privacybeleid",
      description: "Welke gegevens Windy City Wares verzamelt, waarom, en welke keuzes je hebt.",
      sections: [
        { heading: "Wat we verzamelen", bullets: ["Je bestelling: naam, e-mail, telefoon (optioneel), verzendadres en wat je kocht, om te kunnen leveren en je e-mails over je bestelling te sturen.", "Je account, als je er een aanmaakt: e-mail, naam, bewaarde adressen en verlanglijst.", "Je kaartgegevens vul je in op de pagina van Stripe; ze komen nooit bij ons."] },
        { heading: "Bezoekstatistieken (alleen met je toestemming)", paragraphs: ["Als je in de melding akkoord gaat, tellen we bezoeken en wat er bekeken wordt om de winkel te verbeteren: bekeken pagina's, zoekopdrachten, winkelwagenactiviteit en paginasnelheid. We gebruiken geen advertentietrackers, volgen je niet op andere sites en bewaren geen IP-adressen. Zoektermen die op een e-mailadres of telefoonnummer lijken, worden weggegooid. Statistieken worden verwijderd na de bewaartermijn uit onze instellingen. Je kunt je keuze altijd wijzigen via Keuzes voor statistieken onderaan elke pagina."] },
        { heading: "E-mails", paragraphs: ["We sturen e-mails over je bestellingen. Nieuws en aanbiedingen alleen als je daarom vraagt, en elke e-mail heeft een afmeldlink. Winkelwagenherinneringen alleen als je daar bij het afrekenen om vraagt."] },
        { heading: "Met wie we gegevens delen", bullets: ["Stripe, voor kaartbetalingen.", "Onze e-mail- en hostingproviders, om e-mails te versturen en de winkel te laten draaien.", "Vervoerders, om je bestelling te bezorgen.", "We verkopen je gegevens nooit."] },
        { heading: "Je keuzes", paragraphs: ["Neem contact op om je gegevens in te zien, te corrigeren of te laten verwijderen. Afmelden voor marketingmails kan met de link in elke e-mail."] },
      ],
    },
    terms: {
      title: "Verkoopvoorwaarden",
      description: "De voorwaarden die gelden als je bij Windy City Wares bestelt.",
      sections: [
        { heading: "Bestellingen", paragraphs: ["Je bestelling is bevestigd zodra we de betaling hebben ontvangen en je de bevestiging hebben gemaild. Is een artikel niet meer beschikbaar, dan laten we het je weten en betalen we het terug."] },
        { heading: "Prijzen", paragraphs: ["Prijzen zijn in Amerikaanse dollars. Kortingen en aanbiedingen gelden zolang ze lopen; de prijs bij het afrekenen is de prijs die je betaalt. Waar nodig wordt omzetbelasting toegevoegd."] },
        { heading: "Verzending en retouren", paragraphs: ["Zie onze pagina's over verzending en retourneren."] },
        { heading: "Contact", paragraphs: ["Vragen over een bestelling? Gebruik de contactpagina; we antwoorden per e-mail, meestal binnen één werkdag."] },
      ],
    },
  },
};
