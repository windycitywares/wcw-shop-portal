"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useOptionalI18n } from "@/i18n/client";
import { track } from "./analytics";
import { apiFetch } from "./client-api";
import type { Quote } from "./types";

/**
 * The cart lives in localStorage (guests and signed-in shoppers alike). Prices shown come from the server:
 * every change asks POST /cart/quote, which applies sales, offers, the discount code, shipping and tax with the
 * same rules checkout uses, so the shopper never sees one price and pays another.
 */
export interface CartLine {
  key: string; // productId + chosen options
  productId: number;
  slug: string;
  sku: string;
  title: string;
  /** Chosen size/variant as stored (e.g. "10 inch Large"); shown translated in the cart */
  variant?: string;
  /** Last known unit price (refreshed from the server quote) */
  price: number;
  currency: string;
  image?: string;
  options?: Record<string, string>;
  quantity: number;
}

interface CartState {
  lines: CartLine[];
  count: number;
  /** Server subtotal when a quote is in, else the sum of the last known prices */
  subtotal: number;
  isOpen: boolean;
  setOpen: (open: boolean) => void;
  add: (line: Omit<CartLine, "key" | "quantity">, quantity?: number) => void;
  setQuantity: (key: string, quantity: number) => void;
  remove: (key: string) => void;
  clear: () => void;
  /** Replace the whole cart, e.g. from a reminder email link */
  replace: (lines: CartLine[], coupon?: string | null) => void;
  coupon: string | null;
  setCoupon: (code: string | null) => void;
  quote: Quote | null;
  quoting: boolean;
  quoteError: boolean;
}

const STORAGE_KEY = "wcw-cart";
const COUPON_KEY = "wcw-coupon";
const MAX_QTY = 99;
const QUOTE_DELAY_MS = 250;
const CartContext = createContext<CartState | null>(null);

export function lineKey(productId: number, options?: Record<string, string>) {
  const opts = options
    ? Object.entries(options)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => `${k}=${v}`)
        .join("&")
    : "";
  return `${productId}${opts ? `?${opts}` : ""}`;
}

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback; // corrupt or unavailable storage
  }
}

function write(key: string, value: unknown) {
  try {
    if (value == null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable (private mode) */
  }
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const { locale } = useOptionalI18n();
  const [lines, setLines] = useState<CartLine[]>([]);
  const [coupon, setCouponState] = useState<string | null>(null);
  const [isOpen, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [quoting, setQuoting] = useState(false);
  const [quoteError, setQuoteError] = useState(false);
  const request = useRef(0);
  const trackedCode = useRef<string | null>(null);

  useEffect(() => {
    setLines(read<CartLine[]>(STORAGE_KEY, []));
    let code = read<string | null>(COUPON_KEY, null);
    // A campaign link like /shop?code=THANKS10 pre-fills the code.
    try {
      const fromUrl = new URLSearchParams(window.location.search).get("code");
      if (fromUrl && /^[A-Za-z0-9-]{3,40}$/.test(fromUrl)) code = fromUrl.toUpperCase();
    } catch {
      /* no window.location in odd environments */
    }
    setCouponState(code);
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (loaded) write(STORAGE_KEY, lines);
  }, [lines, loaded]);
  useEffect(() => {
    if (loaded) write(COUPON_KEY, coupon);
  }, [coupon, loaded]);

  // Ask the server for prices after every change (debounced; late answers to old carts are ignored).
  useEffect(() => {
    if (!loaded) return;
    if (lines.length === 0) {
      setQuote(null);
      setQuoteError(false);
      return;
    }
    const id = ++request.current;
    setQuoting(true);
    const timer = setTimeout(async () => {
      try {
        const q = await apiFetch<Quote>("/cart/quote", {
          method: "POST",
          body: JSON.stringify({
            items: lines.map((l) => ({ product_id: l.productId, quantity: l.quantity, options: l.options ?? {} })),
            coupon: coupon || undefined,
            lang: locale,
          }),
        });
        if (id !== request.current) return;
        setQuote(q);
        // Count how discount codes fare (once per code), to spot codes that confuse people.
        if (q.coupon && q.coupon.code !== trackedCode.current) {
          trackedCode.current = q.coupon.code;
          track(q.coupon.applied ? "coupon_applied" : "coupon_failed", { data: { reason: q.coupon.reason ?? "ok" } });
        }
        setQuoteError(false);
        // Keep the remembered unit prices in step with the server (sale started or ended, price changed).
        setLines((prev) => {
          let changed = false;
          const next = prev.map((l) => {
            const match = q.lines.find((ql) => lineKey(ql.product_id, ql.options) === lineKey(l.productId, l.options ?? {}));
            if (match && match.unit_price !== l.price) {
              changed = true;
              return { ...l, price: match.unit_price };
            }
            return l;
          });
          return changed ? next : prev;
        });
      } catch {
        if (id === request.current) setQuoteError(true);
      } finally {
        if (id === request.current) setQuoting(false);
      }
    }, QUOTE_DELAY_MS);
    return () => clearTimeout(timer);
    // Prices don't depend on the remembered price, so only quantities, options and the code trigger a new quote.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loaded, coupon, locale, lines.map((l) => `${l.key}*${l.quantity}`).join(",")]);

  const add = useCallback<CartState["add"]>((line, quantity = 1) => {
    const key = lineKey(line.productId, line.options);
    track("add_to_cart", { product_id: line.productId, value: Math.round(line.price * quantity * 100) / 100, data: { quantity } });
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

  const remove = useCallback((key: string) => {
    setLines((prev) => {
      const gone = prev.find((l) => l.key === key);
      if (gone) track("remove_from_cart", { product_id: gone.productId, value: Math.round(gone.price * gone.quantity * 100) / 100 });
      return prev.filter((l) => l.key !== key);
    });
  }, []);
  const clear = useCallback(() => {
    setLines([]);
    setCouponState(null);
  }, []);
  const replace = useCallback((next: CartLine[], code?: string | null) => {
    setLines(next);
    if (code !== undefined) setCouponState(code ? code.toUpperCase() : null);
  }, []);
  const setCoupon = useCallback((code: string | null) => {
    const clean = code?.trim().toUpperCase() || null;
    setCouponState(clean);
  }, []);

  const value = useMemo<CartState>(
    () => ({
      lines,
      count: lines.reduce((n, l) => n + l.quantity, 0),
      subtotal: quote?.subtotal ?? lines.reduce((n, l) => n + l.quantity * l.price, 0),
      isOpen,
      setOpen,
      add,
      setQuantity,
      remove,
      clear,
      replace,
      coupon,
      setCoupon,
      quote,
      quoting,
      quoteError,
    }),
    [lines, isOpen, add, setQuantity, remove, clear, replace, coupon, setCoupon, quote, quoting, quoteError],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartState {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside <CartProvider>");
  return ctx;
}
