"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

/**
 * Guest cart, kept in localStorage. (Next step per spec: sync to the database
 * for signed-in users once the cart API exists.)
 */
export interface CartLine {
  key: string; // productId + chosen options
  productId: number;
  slug: string;
  sku: string;
  title: string;
  /** Chosen size/variant as stored (e.g. "10 inch Large"); shown translated in the cart */
  variant?: string;
  price: number;
  currency: string;
  image?: string;
  options?: Record<string, string>;
  quantity: number;
}

interface CartState {
  lines: CartLine[];
  count: number;
  /** Add-up of the prices saved with each line. The real prices come from the quote (lib/quote.ts). */
  subtotal: number;
  /** The discount code the shopper typed in, kept until they remove it or place an order. */
  coupon: string | null;
  setCoupon: (code: string | null) => void;
  isOpen: boolean;
  setOpen: (open: boolean) => void;
  add: (line: Omit<CartLine, "key" | "quantity">, quantity?: number) => void;
  setQuantity: (key: string, quantity: number) => void;
  remove: (key: string) => void;
  clear: () => void;
}

const STORAGE_KEY = "wcw-cart";
const COUPON_KEY = "wcw-coupon";
const MAX_QTY = 99;
const CartContext = createContext<CartState | null>(null);

function lineKey(productId: number, options?: Record<string, string>) {
  const opts = options
    ? Object.entries(options)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => `${k}=${v}`)
        .join("&")
    : "";
  return `${productId}${opts ? `?${opts}` : ""}`;
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>([]);
  const [coupon, setCouponState] = useState<string | null>(null);
  const [isOpen, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setLines(JSON.parse(saved));
      setCouponState(localStorage.getItem(COUPON_KEY));
    } catch {
      /* ignore corrupt or unavailable storage */
    }
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (!loaded) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
      if (coupon) localStorage.setItem(COUPON_KEY, coupon);
      else localStorage.removeItem(COUPON_KEY);
    } catch {
      /* storage unavailable */
    }
  }, [lines, coupon, loaded]);

  const setCoupon = useCallback((code: string | null) => setCouponState(code?.trim() ? code.trim().toUpperCase() : null), []);

  const add = useCallback<CartState["add"]>((line, quantity = 1) => {
    const key = lineKey(line.productId, line.options);
    setLines((prev) => {
      const existing = prev.find((l) => l.key === key);
      if (existing) {
        return prev.map((l) => (l.key === key ? { ...l, quantity: Math.min(MAX_QTY, l.quantity + quantity) } : l));
      }
      return [...prev, { ...line, key, quantity }];
    });
    setOpen(true);
  }, []);

  const setQuantity = useCallback((key: string, quantity: number) => {
    setLines((prev) =>
      quantity <= 0
        ? prev.filter((l) => l.key !== key)
        : prev.map((l) => (l.key === key ? { ...l, quantity: Math.min(MAX_QTY, quantity) } : l)),
    );
  }, []);

  const remove = useCallback((key: string) => setLines((prev) => prev.filter((l) => l.key !== key)), []);
  const clear = useCallback(() => {
    setLines([]);
    setCouponState(null);
  }, []);

  const value = useMemo<CartState>(
    () => ({
      lines,
      count: lines.reduce((n, l) => n + l.quantity, 0),
      subtotal: lines.reduce((n, l) => n + l.quantity * l.price, 0),
      coupon,
      setCoupon,
      isOpen,
      setOpen,
      add,
      setQuantity,
      remove,
      clear,
    }),
    [lines, coupon, setCoupon, isOpen, add, setQuantity, remove, clear],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartState {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside <CartProvider>");
  return ctx;
}
