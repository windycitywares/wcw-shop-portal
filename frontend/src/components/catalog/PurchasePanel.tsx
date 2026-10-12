"use client";

import { useMemo, useState } from "react";
import { attrKey, attrValue } from "@/i18n/attributes";
import { useI18n } from "@/i18n/client";
import { useCart } from "@/lib/cart";
import type { Product, ProductDetail } from "@/lib/types";
import { attributeList, cn, formatPrice } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Price } from "@/components/ui/misc";

/**
 * Two ways a product offers choices:
 * 1. Real variants (child products with their own SKU/price) -> one row per option, with its price.
 * 2. List-valued attributes with no variants (e.g. Etsy "Size: Small, Large") -> pick options,
 *    which travel with the cart line.
 */
export function PurchasePanel({ product }: { product: ProductDetail }) {
  const { add } = useCart();
  const { t, fmt, locale } = useI18n();
  const hasVariants = product.variants.length > 0;
  const [variantId, setVariantId] = useState<number | null>(hasVariants ? product.variants[0].id : null);
  const optionGroups = useMemo(
    () =>
      hasVariants
        ? []
        : Object.entries(product.attributes)
            .filter(([, v]) => Array.isArray(v) && v.length > 1)
            .map(([key, v]) => ({ key, values: attributeList(v) })),
    [product.attributes, hasVariants],
  );
  const [options, setOptions] = useState<Record<string, string>>(
    Object.fromEntries(optionGroups.map((g) => [g.key, g.values[0]])),
  );
  const [qty, setQty] = useState(1);

  const variant: Product | undefined = product.variants.find((v) => v.id === variantId);
  const active: Product = variant ?? product;
  const soldOut = active.stock_status === "out_of_stock";
  const saving =
    active.compare_at_price && active.compare_at_price > active.base_price
      ? Math.round((1 - active.base_price / active.compare_at_price) * 100)
      : 0;

  /** Stored name of a variant, e.g. "10 inch Large" (from its attributes, else its title). */
  function variantName(v: Product) {
    const attrs = Object.values(v.attributes).map((a) => attributeList(a).join("/"));
    return attrs.length ? attrs.join(", ") : v.title;
  }
  const variantGroupLabel = hasVariants
    ? attrKey(t, Object.keys(product.variants[0].attributes)[0] ?? "Size")
    : t.product.options;

  function onAdd() {
    add(
      {
        productId: active.id,
        slug: product.slug,
        sku: active.sku,
        title: product.title,
        variant: variant ? variantName(variant) : undefined,
        price: active.base_price,
        currency: active.currency,
        image: (active.images[0] ?? product.images[0])?.url,
        options: optionGroups.length ? options : undefined,
      },
      qty,
    );
  }

  return (
    <div className="space-y-7">
      <div>
        <Price
          amount={active.base_price}
          compareAt={active.compare_at_price}
          currency={active.currency}
          locale={locale}
          className="text-2xl"
        />
        <p className="mt-1.5 flex flex-wrap gap-x-3 text-sm">
          <span className={soldOut ? "text-danger" : "text-success"}>
            {t.product.stock[active.stock_status]}
            {active.stock_quantity != null && active.stock_quantity > 0 && active.stock_quantity <= 3 && (
              <span className="text-muted">, {fmt(t.product.onlyLeft, { count: active.stock_quantity })}</span>
            )}
          </span>
          {saving > 0 && <span className="text-sale">{fmt(t.product.save, { percent: saving })}</span>}
        </p>
      </div>

      {hasVariants && (
        <fieldset>
          <legend className="mb-3 font-serif text-lg">{variantGroupLabel}</legend>
          <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
            {product.variants.map((v, i) => {
              const checked = v.id === variantId;
              const out = v.stock_status === "out_of_stock";
              return (
                <label
                  key={v.id}
                  className={cn(
                    "flex cursor-pointer items-center gap-3 px-4 py-3.5 text-[0.9375rem] transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:-outline-offset-2 has-[:focus-visible]:outline-accent",
                    i > 0 && "border-t border-line",
                    checked ? "bg-accent-soft" : "hover:bg-canvas",
                    out && "text-muted line-through",
                  )}
                >
                  <input
                    type="radio"
                    name="variant"
                    value={v.id}
                    checked={checked}
                    onChange={() => setVariantId(v.id)}
                    className="size-4 accent-[var(--color-accent)]"
                  />
                  <span className="flex-1">{attrValue(t, variantName(v))}</span>
                  <span className={cn("tabular-nums", checked ? "font-medium" : "text-muted")}>
                    {formatPrice(v.base_price, v.currency, locale)}
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>
      )}

      {optionGroups.map((group) => (
        <div key={group.key}>
          <label htmlFor={`opt-${group.key}`} className="mb-2 block font-serif text-lg">
            {attrKey(t, group.key)}
          </label>
          <select
            id={`opt-${group.key}`}
            value={options[group.key]}
            onChange={(e) => setOptions((o) => ({ ...o, [group.key]: e.target.value }))}
            className="h-11 w-full max-w-xs rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
          >
            {group.values.map((v) => (
              <option key={v} value={v}>
                {attrValue(t, v)}
              </option>
            ))}
          </select>
        </div>
      ))}

      <div className="flex items-end gap-3">
        <div>
          <label htmlFor="qty" className="mb-2 block text-sm text-muted">
            {t.product.quantity}
          </label>
          <input
            id="qty"
            type="number"
            min={1}
            max={active.stock_quantity ?? 99}
            value={qty}
            onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
            className="h-13 w-20 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-center"
          />
        </div>
        <Button size="lg" className="flex-1" onClick={onAdd} disabled={soldOut}>
          {soldOut ? t.product.soldOut : t.product.addToCart}
        </Button>
      </div>
    </div>
  );
}
