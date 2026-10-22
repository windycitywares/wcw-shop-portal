"use client";

import { ShoppingBag01 } from "@untitledui/icons";
import { useI18n } from "@/i18n/client";
import { useCart } from "@/lib/cart";

export function CartButton() {
  const { count, setOpen } = useCart();
  const { t, fmt } = useI18n();
  return (
    <button
      type="button"
      onClick={() => setOpen(true)}
      title={fmt(t.cart.open, { count })}
      className="relative grid size-10 place-items-center rounded-full hover:bg-sand"
    >
      <ShoppingBag01 aria-hidden="true" className="size-5" strokeWidth={1.6} />
      {count > 0 && (
        <span
          aria-hidden="true"
          className="absolute -right-0.5 -top-0.5 grid min-w-5 place-items-center rounded-full bg-accent px-1 text-[11px] font-semibold text-on-accent"
        >
          {count}
        </span>
      )}
      <span className="sr-only">{fmt(t.cart.open, { count })}</span>
    </button>
  );
}
