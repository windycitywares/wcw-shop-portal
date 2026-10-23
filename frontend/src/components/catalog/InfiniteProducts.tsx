"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/client-api";
import { useI18n } from "@/i18n/client";
import type { Page, Product } from "@/lib/types";
import { ProductGrid } from "./ProductCard";

/**
 * The product grid that keeps filling as the visitor scrolls (like a social feed). The first page is rendered
 * by the server, so it appears at once and search engines see it; further pages are fetched in the background
 * just before the end is reached. A "Load more" button is always there too, for keyboards and slow connections.
 */
export function InfiniteProducts({
  initial,
  total,
  startPage,
  pageSize,
  query,
  priorityCount = 0,
}: {
  initial: Product[];
  total: number;
  startPage: number;
  pageSize: number;
  /** The API query without `page` (filters, sort, page_size, lang). */
  query: string;
  priorityCount?: number;
}) {
  const { locale, t, fmt } = useI18n();
  const [items, setItems] = useState<Product[]>(initial);
  const [page, setPage] = useState(startPage);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const busy = useRef(false);
  const sentinel = useRef<HTMLDivElement | null>(null);
  const done = page * pageSize >= total;

  const more = useCallback(async () => {
    if (busy.current || done) return;
    busy.current = true;
    setLoading(true);
    setFailed(false);
    try {
      const res = await fetch(`${API_URL}/products?${query}&page=${page + 1}`);
      if (!res.ok) throw new Error(String(res.status));
      const body = (await res.json()) as Page<Product>;
      setItems((old) => {
        const seen = new Set(old.map((p) => p.id));
        return [...old, ...body.items.filter((p) => !seen.has(p.id))];
      });
      setPage((p) => (body.items.length === 0 ? Math.ceil(total / pageSize) : p + 1)); // nothing came back: stop asking
    } catch {
      setFailed(true);
    } finally {
      busy.current = false;
      setLoading(false);
    }
  }, [done, page, query]);

  useEffect(() => {
    const el = sentinel.current;
    if (!el || done || failed || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => entries.some((e) => e.isIntersecting) && void more(), { rootMargin: "700px 0px" });
    observer.observe(el);
    return () => observer.disconnect();
  }, [more, done, failed]);

  return (
    <>
      <ProductGrid products={items} locale={locale} priorityCount={priorityCount} columns={3} />
      <div ref={sentinel} className="mt-14 flex flex-col items-center gap-3 text-sm text-muted" aria-live="polite">
        <p>{done ? fmt(t.listing.allShown, { total }) : fmt(t.listing.showing, { shown: items.length, total })}</p>
        {!done && (
          <>
            <div className="h-1 w-48 overflow-hidden rounded-full bg-sand" aria-hidden="true">
              <div className="h-full rounded-full bg-ink/70 transition-[width] duration-500" style={{ width: `${Math.min(100, (items.length / total) * 100)}%` }} />
            </div>
            {failed && <p role="alert">{t.listing.loadError}</p>}
            <button
              type="button"
              onClick={() => void more()}
              disabled={loading}
              className="inline-flex h-10 items-center rounded-full border border-line bg-surface px-6 text-ink hover:border-ink/40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-60"
            >
              {loading ? t.listing.loadingMore : t.listing.loadMore}
            </button>
          </>
        )}
      </div>
    </>
  );
}
