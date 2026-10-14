"use client";

import Link from "next/link";
import { attrKey, attrValue } from "@/i18n/attributes";
import { useI18n } from "@/i18n/client";
import { useCart } from "@/lib/cart";
import type { Quote } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { ProductImage } from "@/components/ui/ProductImage";
import { Badge, Price } from "@/components/ui/misc";

/**
 * The cart's lines. Prices come from the quote when we have one (so sales are applied and a changed price shows),
 * and from what was saved with the line until then.
 */
export function CartLines({ quote = null, onNavigate }: { quote?: Quote | null; onNavigate?: () => void }) {
  const { lines, setQuantity, remove } = useCart();
  const { t, href, fmt, locale } = useI18n();
  return (
    <ul className="divide-y divide-line">
      {lines.map((line) => {
        const priced = quote?.lines.find((l) => l.key === line.key);
        const gone = quote != null && !priced && quote.unavailable.includes(line.productId);
        const unit = priced?.unit_price ?? line.price;
        const was = priced && priced.list_price > priced.unit_price ? priced.list_price : null;
        return (
          <li key={line.key} className="flex gap-4 py-5">
            <div className="mat relative size-24 shrink-0 !p-1.5">
              <div className="relative size-full overflow-hidden">
                <ProductImage src={line.image} alt={line.title} sizes="96px" className="object-contain" />
              </div>
            </div>
            <div className="flex min-w-0 flex-1 flex-col">
              <Link
                href={href(`/product/${line.slug}`)}
                onClick={onNavigate}
                className="font-serif text-lg leading-snug hover:underline"
              >
                {line.title}
              </Link>
              {line.variant && <p className="text-sm text-muted">{attrValue(t, line.variant)}</p>}
              {line.options && Object.keys(line.options).length > 0 && (
                <p className="text-xs text-muted">
                  {Object.entries(line.options)
                    .map(([k, v]) => `${attrKey(t, k)}: ${attrValue(t, v)}`)
                    .join(", ")}
                </p>
              )}
              <p className="flex flex-wrap items-center gap-x-2 text-sm text-muted">
                <Price amount={unit} compareAt={was} currency={line.currency} locale={locale} />
                {was != null && <Badge tone="accent">{priced?.sale_label || t.cart.sale}</Badge>}
              </p>
              {gone && <p className="mt-1 text-xs text-danger">{t.cart.soldOut}</p>}
              {priced?.issue === "limited" && (
                <p className="mt-1 text-xs text-danger">{fmt(t.cart.limited, { count: priced.max_quantity ?? 0 })}</p>
              )}
              <div className="mt-auto flex items-center gap-3 pt-2">
                <div
                  className="flex items-center rounded-full border border-line bg-surface"
                  role="group"
                  aria-label={fmt(t.cart.quantityFor, { title: line.title })}
                >
                  <button
                    type="button"
                    className="grid size-8 place-items-center rounded-full hover:bg-sand"
                    onClick={() => setQuantity(line.key, line.quantity - 1)}
                  >
                    <span aria-hidden="true">−</span>
                    <span className="sr-only">{t.cart.decrease}</span>
                  </button>
                  <span className="w-8 text-center text-sm" aria-live="polite">
                    {line.quantity}
                  </span>
                  <button
                    type="button"
                    className="grid size-8 place-items-center rounded-full hover:bg-sand"
                    onClick={() => setQuantity(line.key, line.quantity + 1)}
                  >
                    <span aria-hidden="true">+</span>
                    <span className="sr-only">{t.cart.increase}</span>
                  </button>
                </div>
                <button type="button" onClick={() => remove(line.key)} className="text-xs text-muted underline hover:text-ink">
                  {t.cart.remove}
                  <span className="sr-only"> {line.title}</span>
                </button>
              </div>
            </div>
            <p className="text-sm font-medium">{formatPrice(unit * line.quantity, line.currency, locale)}</p>
          </li>
        );
      })}
    </ul>
  );
}
