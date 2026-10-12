"use client";

import Link from "next/link";
import { useI18n } from "@/i18n/client";
import { useCart } from "@/lib/cart";
import { site } from "@/lib/site";
import { formatPrice } from "@/lib/utils";
import { CartLines } from "@/components/cart/CartLines";
import { Button } from "@/components/ui/Button";
import { Container, EmptyState } from "@/components/ui/misc";

export default function CartPage() {
  const { lines, subtotal } = useCart();
  const { t, href, locale } = useI18n();
  return (
    <Container className="py-12 sm:py-16">
      <h1 className="text-5xl sm:text-6xl">{t.cart.title}</h1>
      {lines.length === 0 ? (
        <div className="mt-10">
          <EmptyState title={t.cart.empty}>
            <Link href={href("/shop")} className="underline">
              {t.cart.continue}
            </Link>
          </EmptyState>
        </div>
      ) : (
        <div className="mt-10 grid gap-12 lg:grid-cols-[1fr_24rem]">
          <section aria-label={t.cart.items} className="border-t border-line">
            <CartLines />
          </section>
          <aside aria-label={t.cart.orderSummary} className="h-fit rounded-[var(--radius-card)] border border-line bg-surface p-6">
            <h2 className="text-2xl">{t.cart.summary}</h2>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <dt>{t.cart.subtotal}</dt>
                <dd className="font-medium">{formatPrice(subtotal, "USD", locale)}</dd>
              </div>
              <div className="flex justify-between text-muted">
                <dt>{t.cart.shippingTax}</dt>
                <dd>{t.cart.atCheckout}</dd>
              </div>
            </dl>
            {/* Checkout (address -> shipping -> payment review) is the next build step. */}
            <Button size="lg" className="mt-6 w-full" disabled aria-describedby="checkout-note">
              {t.cart.checkout}
            </Button>
            <p id="checkout-note" className="mt-3 text-xs text-muted">
              {t.cart.checkoutSoon}{" "}
              <a href={site.social[0].href} target="_blank" rel="noopener noreferrer" className="underline">
                Etsy
                <span className="sr-only"> {t.footer.newTab}</span>
              </a>
            </p>
          </aside>
        </div>
      )}
    </Container>
  );
}
