"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/i18n/client";
import { lineKey, useCart, type CartLine } from "@/lib/cart";
import { apiFetch } from "@/lib/client-api";
import { site } from "@/lib/site";
import type { Quote } from "@/lib/types";
import { CartLines } from "@/components/cart/CartLines";
import { CartMessages, CartTotals, CouponForm, FreeShippingProgress, RewardHint } from "@/components/cart/CartSummary";
import { Button } from "@/components/ui/Button";
import { Alert, Container, EmptyState } from "@/components/ui/misc";

type Recovered = { items: { product_id: number; quantity: number; options: Record<string, string> }[]; coupon: string | null };

/** /cart?recover=<token> (from a reminder email) puts the saved cart back, priced as of today. */
function useRecoverFromLink() {
  const { replace } = useCart();
  const { locale } = useI18n();
  const [state, setState] = useState<"idle" | "working" | "done" | "failed">("idle");
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const token = new URLSearchParams(window.location.search).get("recover");
    if (!token || !/^[\w-]{10,40}$/.test(token)) return;
    setState("working");
    (async () => {
      try {
        const saved = await apiFetch<Recovered>(`/cart/recover/${encodeURIComponent(token)}`);
        if (!saved.items.length) throw new Error("empty");
        const q = await apiFetch<Quote>("/cart/quote", {
          method: "POST",
          body: JSON.stringify({ items: saved.items, lang: locale }),
        });
        if (!q.lines.length) throw new Error("nothing available");
        const lines: CartLine[] = q.lines.map((l) => ({
          key: lineKey(l.product_id, l.options),
          productId: l.product_id,
          slug: l.slug,
          sku: l.sku,
          title: l.title,
          variant: l.variant ?? undefined,
          price: l.unit_price,
          currency: q.currency,
          image: l.image ?? undefined,
          options: Object.keys(l.options).length ? l.options : undefined,
          quantity: l.quantity,
        }));
        replace(lines, saved.coupon);
        setState("done");
      } catch {
        setState("failed");
      }
      window.history.replaceState(null, "", window.location.pathname); // don't restore again on refresh
    })();
  }, [replace, locale]);
  return state;
}

export default function CartPage() {
  const { lines } = useCart();
  const { t, href } = useI18n();
  const recovery = useRecoverFromLink();
  return (
    <Container className="py-12 sm:py-16">
      <h1 className="text-5xl sm:text-6xl">{t.cart.title}</h1>
      <div className="mt-6 space-y-3" aria-live="polite">
        {recovery === "working" && <p className="text-sm text-muted">{t.cart.restoring}</p>}
        {recovery === "done" && <Alert tone="success">{t.cart.restored}</Alert>}
        {recovery === "failed" && <Alert tone="danger">{t.cart.restoreFailed}</Alert>}
      </div>
      {lines.length === 0 ? (
        <div className="mt-8">
          <EmptyState title={t.cart.empty}>
            <Link href={href("/shop")} className="underline">
              {t.cart.continue}
            </Link>
          </EmptyState>
        </div>
      ) : (
        <div className="mt-8 grid gap-12 lg:grid-cols-[minmax(0,1fr)_24rem]">
          <section aria-label={t.cart.items} className="space-y-4">
            <CartMessages />
            <div className="border-t border-line">
              <CartLines />
            </div>
          </section>
          <aside aria-label={t.cart.orderSummary} className="h-fit space-y-5 rounded-[var(--radius-card)] border border-line bg-surface p-6">
            <h2 className="text-2xl">{t.cart.summary}</h2>
            <FreeShippingProgress />
            <RewardHint />
            <CouponForm />
            <CartTotals />
            {/* Checkout (address -> payment -> review) arrives in the next storefront batch. */}
            <Button size="lg" className="w-full" disabled aria-describedby="checkout-note">
              {t.cart.checkout}
            </Button>
            <p id="checkout-note" className="text-xs text-muted">
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
