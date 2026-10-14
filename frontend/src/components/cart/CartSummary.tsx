"use client";

import { useState } from "react";
import { useI18n } from "@/i18n/client";
import { useCart } from "@/lib/cart";
import { cn, formatPrice } from "@/lib/utils";
import { Button } from "@/components/ui/Button";

/** Progress toward free shipping, from the server quote. Hidden when there's no threshold. */
export function FreeShippingProgress({ className }: { className?: string }) {
  const { quote } = useCart();
  const { t, fmt, locale } = useI18n();
  const ship = quote?.shipping;
  if (!quote || !ship?.free_threshold || !ship.deliverable) return null;
  const done = ship.free || !ship.remaining_for_free;
  const pct = done ? 100 : Math.max(4, Math.min(100, ((ship.free_threshold - (ship.remaining_for_free ?? 0)) / ship.free_threshold) * 100));
  return (
    <div className={className}>
      <p className={cn("text-sm", done ? "text-success" : "text-ink")} aria-live="polite">
        {done
          ? t.cart.freeShippingDone
          : fmt(t.cart.freeShippingLeft, { amount: formatPrice(ship.remaining_for_free ?? 0, quote.currency, locale) })}
      </p>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-sand" aria-hidden="true">
        <div className={cn("h-full rounded-full transition-[width] duration-500", done ? "bg-success" : "bg-accent")} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** "Spend $20 more: 10% off" — the nearest automatic offer the cart hasn't reached yet. */
export function RewardHint({ className }: { className?: string }) {
  const { quote } = useCart();
  const { t, fmt, locale } = useI18n();
  const next = quote?.rewards.find((r) => (r.remaining_amount ?? 0) > 0 || (r.remaining_qty ?? 0) > 0);
  if (!quote || !next) return null;
  const text =
    next.remaining_amount != null && next.remaining_amount > 0
      ? fmt(t.cart.rewardHint, { amount: formatPrice(next.remaining_amount, quote.currency, locale), name: next.name })
      : fmt(t.cart.rewardQtyHint, { count: next.remaining_qty ?? 0, name: next.name });
  return <p className={cn("text-sm text-accent", className)}>{text}</p>;
}

export function CouponForm() {
  const { coupon, setCoupon, quote, quoting } = useCart();
  const { t, fmt } = useI18n();
  const [draft, setDraft] = useState("");
  const status = quote?.coupon;
  if (coupon) {
    const ok = status?.applied;
    const problem = status && !status.applied ? status.message : null;
    return (
      <div className="space-y-1.5 text-sm">
        <div className="flex items-center justify-between gap-3">
          <span className={cn("font-medium", ok ? "text-success" : "text-ink")}>
            {ok ? fmt(t.cart.couponApplied, { code: coupon }) : coupon}
          </span>
          <button type="button" onClick={() => setCoupon(null)} className="text-xs text-muted underline hover:text-ink">
            {t.cart.couponRemove}
          </button>
        </div>
        {!quoting && problem && (
          <p role="alert" className="text-danger">
            {fmt(t.cart.couponNotUsed, { code: coupon })}: {problem}
          </p>
        )}
      </div>
    );
  }
  return (
    <form
      className="flex gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (draft.trim()) setCoupon(draft);
        setDraft("");
      }}
    >
      <label htmlFor="coupon" className="sr-only">
        {t.cart.couponLabel}
      </label>
      <input
        id="coupon"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder={t.cart.couponLabel}
        autoComplete="off"
        autoCapitalize="characters"
        maxLength={40}
        className="min-w-0 flex-1 rounded-[var(--radius-control)] border border-line bg-surface px-4 py-2 text-sm uppercase placeholder:normal-case focus-visible:outline-2 focus-visible:outline-accent"
      />
      <Button type="submit" variant="secondary" size="sm" disabled={!draft.trim()}>
        {t.cart.couponApply}
      </Button>
    </form>
  );
}

/** Totals from the server quote. Falls back to the remembered subtotal if prices couldn't be checked. */
export function CartTotals({ compact = false }: { compact?: boolean }) {
  const { quote, quoting, quoteError, subtotal } = useCart();
  const { t, locale } = useI18n();
  const money = (n: number) => formatPrice(n, quote?.currency ?? "USD", locale);
  if (!quote) {
    return (
      <dl className="space-y-2 text-sm">
        <div className="flex justify-between">
          <dt>{t.cart.subtotal}</dt>
          <dd className="font-medium">{money(subtotal)}</dd>
        </div>
        {quoteError && <p className="text-xs text-muted">{t.cart.pricesUnavailable}</p>}
      </dl>
    );
  }
  const shipping = quote.shipping;
  return (
    <div aria-busy={quoting}>
      <dl className="space-y-2 text-sm">
        <div className="flex justify-between">
          <dt>{t.cart.subtotal}</dt>
          <dd>{money(quote.subtotal)}</dd>
        </div>
        {!compact && quote.sale_savings > 0 && (
          <div className="flex justify-between text-sale">
            <dt>{t.cart.saleSavings}</dt>
            <dd>−{money(quote.sale_savings)}</dd>
          </div>
        )}
        {quote.discounts
          .filter((d) => d.amount > 0)
          .map((d) => (
            <div key={`${d.type}-${d.code ?? d.label}`} className="flex justify-between text-sale">
              <dt>{d.label}</dt>
              <dd>−{money(d.amount)}</dd>
            </div>
          ))}
        <div className="flex justify-between">
          <dt>{t.cart.shipping}</dt>
          <dd>{shipping.free || shipping.amount === 0 ? t.cart.free : money(shipping.amount)}</dd>
        </div>
        {quote.tax && quote.tax.amount > 0 && (
          <div className="flex justify-between">
            <dt>{quote.tax.label}</dt>
            <dd>{money(quote.tax.amount)}</dd>
          </div>
        )}
        <div className="flex justify-between border-t border-line pt-3 text-base">
          <dt className="font-medium">{quote.tax_pending ? t.cart.estimatedTotal : t.cart.total}</dt>
          <dd className="font-medium tabular-nums">{money(quote.total)}</dd>
        </div>
      </dl>
      {quote.tax_pending && <p className="mt-2 text-xs text-muted">{t.cart.taxLater}</p>}
      {quoting && <span className="sr-only" role="status">{t.cart.updating}</span>}
    </div>
  );
}

/** Notes from the server about lines that changed (sold out, fewer left, no longer available). */
export function CartMessages() {
  const { quote } = useCart();
  if (!quote?.messages.length) return null;
  return (
    <ul role="status" className="space-y-1 rounded-[var(--radius-card)] border border-line bg-accent-soft px-4 py-3 text-sm text-ink">
      {quote.messages.map((m) => (
        <li key={m}>{m}</li>
      ))}
    </ul>
  );
}
