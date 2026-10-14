"use client";

import { useI18n } from "@/i18n/client";
import type { Quote } from "@/lib/types";
import { cn, formatPrice } from "@/lib/utils";

/**
 * The money lines of an order, from a quote. Shipping and tax only appear once they're known
 * (the cart page doesn't know the address yet, so it says they're worked out at checkout).
 */
export function Totals({ quote, showTotal = false, className }: { quote: Quote; showTotal?: boolean; className?: string }) {
  const { t, locale } = useI18n();
  const money = (n: number) => formatPrice(n, quote.currency, locale);
  const saved = quote.sale_savings + (quote.coupon?.discount ?? 0) + quote.shipping_discount;
  return (
    <dl className={cn("space-y-2 text-sm", className)}>
      <div className="flex justify-between gap-4">
        <dt>{t.cart.subtotal}</dt>
        <dd className="font-medium tabular-nums">{money(quote.subtotal)}</dd>
      </div>
      {quote.coupon && quote.coupon.discount > 0 && (
        <div className="flex justify-between gap-4 text-success">
          <dt>
            {t.cart.discount} <span className="whitespace-nowrap">({quote.coupon.code})</span>
          </dt>
          <dd className="tabular-nums">−{money(quote.coupon.discount)}</dd>
        </div>
      )}
      {showTotal ? (
        <>
          <div className="flex justify-between gap-4">
            <dt>{t.cart.shipping}</dt>
            <dd className="tabular-nums">{quote.shipping_method ? (quote.shipping_total > 0 ? money(quote.shipping_total) : t.cart.free) : "—"}</dd>
          </div>
          {quote.tax_lines.map((tax) => (
            <div key={tax.name} className="flex justify-between gap-4 text-muted">
              <dt>{tax.name}</dt>
              <dd className="tabular-nums">{money(tax.amount)}</dd>
            </div>
          ))}
          <div className="flex justify-between gap-4 border-t border-line pt-3 text-base">
            <dt className="font-medium">{t.cart.total}</dt>
            <dd className="font-medium tabular-nums">{money(quote.total)}</dd>
          </div>
        </>
      ) : (
        <div className="flex justify-between gap-4 text-muted">
          <dt>{t.cart.shippingTax}</dt>
          <dd>{t.cart.atCheckout}</dd>
        </div>
      )}
      {saved > 0 && <p className="pt-1 text-success">{t.cart.youSave.replace("{amount}", money(saved))}</p>}
    </dl>
  );
}
