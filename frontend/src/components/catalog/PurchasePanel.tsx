"use client";

import { useEffect, useMemo, useState } from "react";
import { attrKey, attrValue } from "@/i18n/attributes";
import { useI18n } from "@/i18n/client";
import { useCart } from "@/lib/cart";
import type { Product, ProductDetail } from "@/lib/types";
import { attributeList, cn, displayPrice, formatPrice, percentOff } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Price } from "@/components/ui/misc";
import { StockRequestDialog, optionGroups as requestOptionGroups } from "@/components/product/StockRequestDialog";
import { API_URL } from "@/lib/client-api";
import { WishlistButton } from "@/components/product/WishlistButton";

/**
 * Two ways a product offers choices:
 * 1. Real variants (child products with their own SKU/price) -> one row per option, with its price.
 * 2. List-valued attributes with no variants (e.g. Etsy "Size: Small, Large") -> pick options,
 *    which travel with the cart line.
 */
export function PurchasePanel({ product: initial }: { product: ProductDetail }) {
  const { add } = useCart();
  // The page itself is cached for a minute: re-read stock in the browser so a design that just sold shows it at once.
  const [product, setProduct] = useState(initial);
  useEffect(() => {
    let live = true;
    fetch(`${API_URL}/products/${encodeURIComponent(initial.slug)}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((fresh: ProductDetail | null) => {
        if (!live || !fresh) return;
        const stock = (p: Product) => ({ stock_status: p.stock_status, stock_quantity: p.stock_quantity });
        setProduct((cur) => ({
          ...cur,
          ...stock(fresh),
          variants: cur.variants.map((v) => {
            const f = fresh.variants.find((x) => x.id === v.id);
            return f ? { ...v, ...stock(f) } : v;
          }),
        }));
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [initial.slug]);
  const [requestOpen, setRequestOpen] = useState<null | "notify" | "other">(null);
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
  const requestGroups = useMemo(() => requestOptionGroups(product), [product]);

  const variant: Product | undefined = product.variants.find((v) => v.id === variantId);
  const active: Product = variant ?? product;
  // A product marked out of stock switches off all of its variants, whatever their own stock says.
  const productOff = hasVariants && product.stock_status === "out_of_stock";
  const soldOut = productOff || active.stock_status === "out_of_stock";
  const price = displayPrice(active);
  const saving = percentOff(price.amount, price.compareAt);
  const saleEnds = active.sale_price != null && active.sale_ends_at ? new Date(active.sale_ends_at) : null;

  /** Stored name of a variant, e.g. "10 inch Large" (from its attributes, else its title). */
  function variantName(v: Product) {
    const attrs = Object.values(v.attributes).map((a) => attributeList(a).join("/"));
    return attrs.length ? attrs.join(", ") : v.title;
  }
  const variantGroupLabel = hasVariants
    ? attrKey(t, Object.keys(product.variants[0].attributes)[0] ?? "Size")
    : t.product.options;

  // What is chosen on the page, in the dialog's terms ({"Size": "Large", ...}).
  const currentChoice = useMemo<Record<string, string>>(() => {
    if (variant) return Object.fromEntries(Object.entries(variant.attributes).map(([k, v]) => [k, attributeList(v)[0]]));
    return options;
  }, [variant, options]);

  function onAdd() {
    add(
      {
        productId: active.id,
        slug: product.slug,
        sku: active.sku,
        title: product.title,
        variant: variant ? variantName(variant) : undefined,
        price: price.amount,
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
        {active.sale_price != null && active.sale_label && (
          <p className="mb-1 text-sm font-medium text-sale">{active.sale_label}</p>
        )}
        <Price
          amount={price.amount}
          compareAt={price.compareAt}
          currency={active.currency}
          locale={locale}
          className="text-2xl"
        />
        <p className="mt-1.5 flex flex-wrap gap-x-3 text-sm">
          <span className={soldOut ? "text-danger" : "text-success"}>
            {t.product.stock[productOff ? "out_of_stock" : active.stock_status]}
            {active.stock_quantity != null && active.stock_quantity > 0 && active.stock_quantity <= 3 && (
              <span className="text-muted">, {fmt(t.product.onlyLeft, { count: active.stock_quantity })}</span>
            )}
          </span>
          {saving > 0 && <span className="text-sale">{fmt(t.product.save, { percent: saving })}</span>}
          {saleEnds && (
            <span className="text-muted">
              {fmt(t.product.saleEnds, {
                date: saleEnds.toLocaleDateString(locale, { month: "long", day: "numeric" }),
              })}
            </span>
          )}
        </p>
      </div>

      {hasVariants && (
        <fieldset>
          <legend className="mb-3 font-serif text-lg">{variantGroupLabel}</legend>
          <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
            {product.variants.map((v, i) => {
              const checked = v.id === variantId;
              const out = productOff || v.stock_status === "out_of_stock";
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
                    {formatPrice(displayPrice(v).amount, v.currency, locale)}
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
      {soldOut && (
        <Button variant="secondary" size="lg" className="w-full" onClick={() => setRequestOpen("notify")}>
          {t.stockRequest.open}
        </Button>
      )}
      {!soldOut && requestGroups.length > 0 && (
        <p className="text-sm text-muted">
          {t.stockRequest.other}{" "}
          <button type="button" className="font-medium text-accent underline underline-offset-4" onClick={() => setRequestOpen("other")}>
            {t.stockRequest.otherLink}
          </button>
        </p>
      )}
      <StockRequestDialog
        product={product}
        open={requestOpen !== null}
        onOpenChange={(o) => !o && setRequestOpen(null)}
        mode={requestOpen ?? "notify"}
        initial={currentChoice}
      />
      <WishlistButton productId={product.id} />
    </div>
  );
}
