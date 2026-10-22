"use client";

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
      <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M5 8h14l-1.2 11.1a2 2 0 0 1-2 1.9H8.2a2 2 0 0 1-2-1.9L5 8Z" strokeLinejoin="round" />
        <path d="M9 8V6a3 3 0 0 1 6 0v2" />
      </svg>
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
