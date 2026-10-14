"use client";

import { useI18n } from "@/i18n/client";
import type { Quote } from "@/lib/types";
import { formatPrice } from "@/lib/utils";

/** A quiet note on how close the order is to free shipping. Says nothing when the shop has no such rule. */
export function FreeShippingMeter({ quote }: { quote: Quote }) {
  const { t, fmt, locale } = useI18n();
  const threshold = quote.free_shipping_threshold;
  if (threshold == null || threshold <= 0) return null;
  const remaining = quote.free_shipping_remaining ?? 0;
  const reached = remaining <= 0;
  const share = reached ? 1 : Math.max(0, Math.min(1, 1 - remaining / threshold));
  return (
    <div className="rounded-lg bg-accent-soft px-4 py-3 text-sm text-accent-strong" role="status">
      <p>
        {reached
          ? t.cart.freeShippingReached
          : fmt(t.cart.freeShippingAway, { amount: formatPrice(remaining, quote.currency, locale) })}
      </p>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface" aria-hidden="true">
        <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${Math.round(share * 100)}%` }} />
      </div>
    </div>
  );
}
