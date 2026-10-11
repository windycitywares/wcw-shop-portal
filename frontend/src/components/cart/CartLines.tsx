"use client";

import Link from "next/link";
import { useCart } from "@/lib/cart";
import { formatPrice } from "@/lib/utils";
import { ProductImage } from "@/components/ui/ProductImage";

export function CartLines({ onNavigate }: { onNavigate?: () => void }) {
  const { lines, setQuantity, remove } = useCart();
  return (
    <ul className="divide-y divide-line">
      {lines.map((line) => (
        <li key={line.key} className="flex gap-4 py-4">
          <div className="relative size-20 shrink-0 overflow-hidden rounded-lg bg-sand">
            <ProductImage src={line.image} alt={line.title} sizes="80px" />
          </div>
          <div className="flex min-w-0 flex-1 flex-col">
            <Link href={`/product/${line.slug}`} onClick={onNavigate} className="truncate font-medium hover:underline">
              {line.title}
            </Link>
            {line.options && Object.keys(line.options).length > 0 && (
              <p className="text-xs text-muted">
                {Object.entries(line.options)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(" · ")}
              </p>
            )}
            <p className="text-sm text-muted">{formatPrice(line.price, line.currency)}</p>
            <div className="mt-auto flex items-center gap-3 pt-2">
              <div className="flex items-center rounded-full border border-line" role="group" aria-label={`Quantity for ${line.title}`}>
                <button
                  type="button"
                  className="grid size-8 place-items-center rounded-full hover:bg-sand"
                  onClick={() => setQuantity(line.key, line.quantity - 1)}
                >
                  <span aria-hidden="true">−</span>
                  <span className="sr-only">Decrease quantity</span>
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
                  <span className="sr-only">Increase quantity</span>
                </button>
              </div>
              <button type="button" onClick={() => remove(line.key)} className="text-xs text-muted underline hover:text-ink">
                Remove<span className="sr-only"> {line.title}</span>
              </button>
            </div>
          </div>
          <p className="text-sm font-medium">{formatPrice(line.price * line.quantity, line.currency)}</p>
        </li>
      ))}
    </ul>
  );
}
