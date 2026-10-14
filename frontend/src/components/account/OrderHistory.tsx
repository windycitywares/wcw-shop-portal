"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { intlLocale } from "@/i18n/config";
import { useI18n } from "@/i18n/client";
import { apiFetch } from "@/lib/client-api";
import type { OrderListItem, Page } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { STATUS_TONE } from "@/components/orders/status";
import { Button } from "@/components/ui/Button";
import { Alert, Badge } from "@/components/ui/misc";

const PAGE_SIZE = 10;

/** The signed-in customer's orders, newest first. */
export function OrderHistory() {
  const { t, href, fmt, locale } = useI18n();
  const [orders, setOrders] = useState<OrderListItem[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (next: number) => {
      setBusy(true);
      try {
        const res = await apiFetch<Page<OrderListItem>>(`/account/orders?page=${next}&page_size=${PAGE_SIZE}`);
        setOrders((prev) => (next === 1 ? res.items : [...(prev ?? []), ...res.items]));
        setTotal(res.total);
        setPage(next);
        setError(false);
      } catch {
        setError(true);
        setOrders((prev) => prev ?? []);
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  useEffect(() => {
    void load(1);
  }, [load]);

  const date = (iso: string | null) => (iso ? new Intl.DateTimeFormat(intlLocale[locale], { dateStyle: "medium" }).format(new Date(iso)) : "");

  return (
    <section aria-labelledby="orders-heading" className="mt-6 rounded-[var(--radius-card)] border border-line bg-surface p-6">
      <h2 id="orders-heading" className="text-2xl">
        {t.account.orders}
      </h2>
      {error && (
        <Alert tone="danger" className="mt-4">
          {t.account.ordersError}
        </Alert>
      )}
      {orders === null ? (
        <p className="mt-2 text-sm text-muted">{t.account.loading}</p>
      ) : orders.length === 0 && !error ? (
        <p className="mt-2 text-sm text-muted">
          {t.account.ordersEmpty}{" "}
          <Link href={href("/shop")} className="underline">
            {t.account.keepShopping}
          </Link>
        </p>
      ) : (
        <>
          <ul className="mt-4 divide-y divide-line border-y border-line">
            {orders.map((o) => (
              <li key={o.number} className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1 py-3 text-sm">
                <div>
                  <Link href={href(`/order/${o.number}`)} className="font-medium text-accent underline underline-offset-2">
                    {t.account.orderNumber} {o.number}
                  </Link>
                  {o.placed_at && <p className="text-muted">{fmt(t.order.placed, { date: date(o.placed_at) })}</p>}
                </div>
                <div className="flex items-center gap-4">
                  <Badge tone={STATUS_TONE[o.status]}>{t.order.status[o.status] ?? o.status}</Badge>
                  <span className="font-medium tabular-nums">{formatPrice(o.grand_total, "USD", locale)}</span>
                </div>
              </li>
            ))}
          </ul>
          {orders.length < total && (
            <Button variant="secondary" size="sm" className="mt-4" disabled={busy} onClick={() => void load(page + 1)}>
              {t.account.showMore}
            </Button>
          )}
        </>
      )}
    </section>
  );
}
