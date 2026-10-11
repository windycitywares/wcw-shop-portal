"use client";

import { useMemo, useState } from "react";
import { useCart } from "@/lib/cart";
import type { Product, ProductDetail } from "@/lib/types";
import { STOCK_LABEL, attributeList, cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Price } from "@/components/ui/misc";

/**
 * Two ways a product offers choices:
 * 1. Real variants (child products with their own SKU/price) -> pick one.
 * 2. List-valued attributes with no variants (e.g. Etsy "Size: Small, Large") -> pick options,
 *    which travel with the cart line.
 */
export function PurchasePanel({ product }: { product: ProductDetail }) {
  const { add } = useCart();
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

  function variantLabel(v: Product) {
    const attrs = Object.values(v.attributes).map((a) => attributeList(a).join("/"));
    return attrs.length ? attrs.join(" · ") : v.title;
  }

  function onAdd() {
    add(
      {
        productId: active.id,
        slug: product.slug,
        sku: active.sku,
        title: variant ? `${product.title} — ${variantLabel(variant)}` : product.title,
        price: active.base_price,
        currency: active.currency,
        image: (active.images[0] ?? product.images[0])?.url,
        options: optionGroups.length ? options : undefined,
      },
      qty,
    );
  }

  return (
    <div className="space-y-6">
      <Price amount={active.base_price} compareAt={active.compare_at_price} currency={active.currency} className="text-2xl" />
      <p className={cn("text-sm", soldOut ? "text-danger" : "text-success")}>
        {STOCK_LABEL[active.stock_status]}
        {active.stock_quantity != null && active.stock_quantity > 0 && active.stock_quantity <= 3 && (
          <span className="text-muted"> — only {active.stock_quantity} left</span>
        )}
      </p>

      {hasVariants && (
        <fieldset>
          <legend className="mb-2 text-sm font-semibold">Options</legend>
          <div className="flex flex-wrap gap-2">
            {product.variants.map((v) => (
              <label
                key={v.id}
                className={cn(
                  "cursor-pointer rounded-full border px-4 py-2 text-sm has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent",
                  v.id === variantId ? "border-ink bg-ink text-white" : "border-line bg-surface hover:border-ink/40",
                  v.stock_status === "out_of_stock" && "line-through opacity-60",
                )}
              >
                <input
                  type="radio"
                  name="variant"
                  value={v.id}
                  checked={v.id === variantId}
                  onChange={() => setVariantId(v.id)}
                  className="sr-only"
                />
                {variantLabel(v)}
              </label>
            ))}
          </div>
        </fieldset>
      )}

      {optionGroups.map((group) => (
        <div key={group.key}>
          <label htmlFor={`opt-${group.key}`} className="mb-2 block text-sm font-semibold">
            {group.key}
          </label>
          <select
            id={`opt-${group.key}`}
            value={options[group.key]}
            onChange={(e) => setOptions((o) => ({ ...o, [group.key]: e.target.value }))}
            className="h-11 w-full max-w-xs rounded-lg border border-line bg-surface px-3 text-sm"
          >
            {group.values.map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </div>
      ))}

      <div className="flex items-end gap-3">
        <div>
          <label htmlFor="qty" className="mb-2 block text-sm font-semibold">
            Quantity
          </label>
          <input
            id="qty"
            type="number"
            min={1}
            max={active.stock_quantity ?? 99}
            value={qty}
            onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
            className="h-12 w-20 rounded-lg border border-line bg-surface px-3 text-center"
          />
        </div>
        <Button size="lg" className="flex-1 sm:flex-none sm:px-12" onClick={onAdd} disabled={soldOut}>
          {soldOut ? "Sold out" : "Add to cart"}
        </Button>
      </div>
    </div>
  );
}
