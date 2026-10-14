"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useI18n } from "@/i18n/client";
import { useCart } from "@/lib/cart";
import { useQuote } from "@/lib/quote";
import { useShopConfig } from "@/lib/shop";
import { site } from "@/lib/site";
import { formatPrice } from "@/lib/utils";
import { CartLines } from "@/components/cart/CartLines";
import { CouponBox } from "@/components/cart/CouponBox";
import { FreeShippingMeter } from "@/components/cart/FreeShippingMeter";
import { Totals } from "@/components/cart/Totals";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Alert, Container, EmptyState } from "@/components/ui/misc";

export default function CartPage() {
  const { lines, subtotal, coupon } = useCart();
  const { t, href, locale } = useI18n();
  const config = useShopConfig();
  const input = useMemo(() => ({ lines, coupon }), [lines, coupon]);
  const { quote, quoteCoupon, loading, error, refresh } = useQuote(input);

  // Anything in the cart that can't be bought as it stands has to be fixed before checking out.
  const needsAttention = quote != null && (quote.unavailable.length > 0 || quote.lines.some((l) => l.issue != null));
  const open = config?.checkout_enabled === true;

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
          <section aria-label={t.cart.items} aria-busy={loading} className="border-t border-line">
            <CartLines quote={quote} />
          </section>
          <aside aria-label={t.cart.orderSummary} className="h-fit space-y-5 rounded-[var(--radius-card)] border border-line bg-surface p-6">
            <h2 className="text-2xl">{t.cart.summary}</h2>
            {quote && <FreeShippingMeter quote={quote} />}
            <CouponBox quote={quote} quoteCoupon={quoteCoupon} loading={loading} />
            {quote ? (
              <Totals quote={quote} className={loading ? "opacity-60 transition-opacity" : "transition-opacity"} />
            ) : (
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt>{t.cart.subtotal}</dt>
                  <dd className="font-medium">{formatPrice(subtotal, "USD", locale)}</dd>
                </div>
                <div className="flex justify-between text-muted">
                  <dt>{t.cart.shippingTax}</dt>
                  <dd>{t.cart.atCheckout}</dd>
                </div>
              </dl>
            )}
            {error && (
              <Alert tone="danger">
                {t.cart.priceError}{" "}
                <button type="button" onClick={refresh} className="underline">
                  {t.cart.retry}
                </button>
              </Alert>
            )}
            {open && !needsAttention ? (
              <ButtonLink href={href("/checkout")} size="lg" className="w-full">
                {t.cart.checkout}
              </ButtonLink>
            ) : (
              <>
                <Button size="lg" className="w-full" disabled aria-describedby="checkout-note">
                  {t.cart.checkout}
                </Button>
                <p id="checkout-note" className="text-xs text-muted">
                  {needsAttention ? (
                    t.checkout.fixCart
                  ) : (
                    <>
                      {t.cart.checkoutSoon}{" "}
                      <a href={site.social[0].href} target="_blank" rel="noopener noreferrer" className="underline">
                        Etsy
                        <span className="sr-only"> {t.footer.newTab}</span>
                      </a>
                    </>
                  )}
                </p>
              </>
            )}
          </aside>
        </div>
      )}
    </Container>
  );
}
