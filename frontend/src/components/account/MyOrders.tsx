"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/client";
import { apiFetch } from "@/lib/client-api";
import type { OrderStatus, Page } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { ProductImage } from "@/components/ui/ProductImage";

interface OrderSummary {
  id: number;
  number: string;
  status: OrderStatus;
  grand_total: number;
  placed_at: string | null;
  item_count: number;
  first_item_title: string | null;
  first_item_image: string | null;
  access_token: string | null;
}

/** The signed-in shopper's orders, newest first, each linking to its private order page. */
export function MyOrders() {
  const { t, fmt, href, locale } = useI18n();
  const [orders, setOrders] = useState<OrderSummary[] | null>(null);
  useEffect(() => {
    apiFetch<Page<OrderSummary>>("/account/orders?page_size=20")
      .then((p) => setOrders(p.items))
      .catch(() => setOrders([]));
  }, []);
  return (
    <section aria-labelledby="my-orders" className="mt-12">
      <h2 id="my-orders" className="text-3xl">
        {t.account.ordersTitle}
      </h2>
      {orders === null ? (
        <p className="mt-4 text-sm text-muted">{t.account.loading}</p>
      ) : orders.length === 0 ? (
        <p className="mt-4 text-sm text-muted">{t.account.ordersEmpty}</p>
      ) : (
        <ul className="mt-4 divide-y divide-line border-y border-line">
          {orders.map((o) => (
            <li key={o.id} className="flex items-center gap-4 py-4">
              <div className="relative size-14 shrink-0 overflow-hidden rounded-md bg-sand">
                <ProductImage src={o.first_item_image ?? undefined} alt="" sizes="56px" className="object-contain" />
              </div>
              <div className="min-w-0 flex-1 text-sm">
                <Link href={href(`/order/${o.access_token}`)} className="font-medium hover:underline">
                  {o.number}
                  <span className="sr-only"> {fmt(t.account.ordersView, { number: o.number })}</span>
                </Link>
                <p className="truncate text-muted">
                  {o.placed_at ? new Date(o.placed_at).toLocaleDateString(locale, { year: "numeric", month: "short", day: "numeric" }) : ""} ·{" "}
                  {o.item_count === 1 ? t.account.ordersOne : fmt(t.account.ordersItems, { count: o.item_count })}
                  {o.first_item_title ? ` · ${o.first_item_title}` : ""}
                </p>
              </div>
              <div className="text-right text-sm">
                <p className="font-medium tabular-nums">{formatPrice(o.grand_total, "USD", locale)}</p>
                <p className="text-muted">{t.order.status[o.status] ?? o.status}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
