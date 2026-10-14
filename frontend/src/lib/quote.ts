"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { CartLine } from "./cart";
import { apiFetch } from "./client-api";
import type { Quote } from "./types";

export interface QuoteInput {
  lines: CartLine[];
  coupon?: string | null;
  shippingMethod?: string | null;
  /** Only sent together with a code (personal and first-order codes depend on who is asking). */
  email?: string | null;
  country?: string | null;
  region?: string | null;
  postalCode?: string | null;
}

/** The items as the API wants them. `key` comes back on each quote line so the cart can match them up. */
export function cartItems(lines: CartLine[]) {
  return lines.map((l) => ({ product_id: l.productId, quantity: l.quantity, options: l.options ?? {}, key: l.key }));
}

function body(input: QuoteInput) {
  const country = input.country && /^[A-Za-z]{2}$/.test(input.country) ? input.country : null;
  return JSON.stringify({
    items: cartItems(input.lines),
    coupon_code: input.coupon || null,
    shipping_method: input.shippingMethod || null,
    email: input.coupon && input.email ? input.email : null,
    country,
    region: input.region || null,
    postal_code: input.postalCode || null,
  });
}

/**
 * Prices the cart on the server (sales, code, shipping, tax). Changes are sent after a short pause,
 * and an answer that arrives late for an older cart is thrown away.
 */
export function useQuote(input: QuoteInput, enabled = true, delay = 300) {
  // The code the stored quote was priced with, so a late "invalid code" answer is never blamed on a newer code.
  const [priced, setPriced] = useState<{ quote: Quote | null; coupon: string | null }>({ quote: null, coupon: null });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  const payload = useMemo(() => body(input), [input]);
  const empty = input.lines.length === 0;

  useEffect(() => {
    if (!enabled || empty) {
      setPriced({ quote: null, coupon: null });
      setLoading(false);
      return;
    }
    setLoading(true);
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const next = await apiFetch<Quote>("/checkout/quote", { method: "POST", body: payload, signal: controller.signal });
        setPriced({ quote: next, coupon: (JSON.parse(payload) as { coupon_code: string | null }).coupon_code });
        setError(null);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Something went wrong");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, delay);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [payload, enabled, empty, delay, tick]);

  const refresh = useCallback(() => setTick((n) => n + 1), []);
  return { quote: priced.quote, quoteCoupon: priced.coupon, loading, error, refresh };
}
