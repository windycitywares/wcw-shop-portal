"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { attrKey, attrValue } from "@/i18n/attributes";
import { useI18n } from "@/i18n/client";
import { stockRequests, type StockRequest } from "@/lib/engagement";
import { Button } from "@/components/ui/Button";
import { ProductImage } from "@/components/ui/ProductImage";

/** The customer's "notify me" and special requests, newest first, with a way to cancel the ones still waiting. */
export function MyStockRequests() {
  const { t, fmt, href, locale } = useI18n();
  const [items, setItems] = useState<StockRequest[] | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    stockRequests.mine().then(setItems, () => setItems([]));
  }, []);

  if (items === null) return null;
  const status = { waiting: t.stockRequest.statusWaiting, notified: t.stockRequest.statusNotified, closed: t.stockRequest.statusClosed };

  return (
    <section id="my-stock-requests" aria-labelledby="my-stock-requests-heading" className="mt-12 scroll-mt-24">
      <h2 id="my-stock-requests-heading" className="text-3xl">
        {t.stockRequest.myTitle}
      </h2>
      {notice && (
        <p role="status" className="mt-3 text-sm text-success">
          {notice}
        </p>
      )}
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-muted">{t.stockRequest.myEmpty}</p>
      ) : (
        <ul className="mt-4 divide-y divide-line rounded-[var(--radius-card)] border border-line bg-surface">
          {items.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-4 p-4">
              <div className="relative size-16 shrink-0 overflow-hidden rounded bg-sand">
                <ProductImage src={r.image} alt="" sizes="64px" />
              </div>
              <div className="min-w-0 flex-1 basis-48">
                <Link href={href(`/product/${r.slug}`)} className="font-medium hover:underline">
                  {r.title}
                </Link>
                {Object.keys(r.options).length > 0 && (
                  <p className="text-sm text-muted">
                    {Object.entries(r.options)
                      .map(([k, v]) => `${attrKey(t, k)}: ${attrValue(t, v)}`)
                      .join(" · ")}
                  </p>
                )}
                <p className="mt-0.5 text-xs text-muted">
                  {r.kind === "request" ? t.stockRequest.kindRequest : t.stockRequest.kindRestock} ·{" "}
                  {fmt(t.stockRequest.requested, { date: new Date(r.created_at).toLocaleDateString(locale, { dateStyle: "medium" }) })} ·{" "}
                  <span className={r.status === "notified" ? "text-success" : undefined}>{status[r.status]}</span>
                </p>
              </div>
              {r.status === "waiting" && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    await stockRequests.cancel(r.id);
                    setItems((list) => (list ?? []).map((x) => (x.id === r.id ? { ...x, status: "closed" } : x)));
                    setNotice(t.stockRequest.cancelled);
                  }}
                >
                  {t.stockRequest.cancel}
                  <span className="sr-only"> {r.title}</span>
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
