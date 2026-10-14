"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import type { OrderListItem, OrderStatus, Page } from "@/lib/types";
import { formatPrice } from "@/lib/utils";
import { PROVIDER_LABEL, STATUS_LABEL, STATUS_TONE, fmtDateTime } from "@/components/admin/orders/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/misc";

const PAGE_SIZE = 25;

/** Each tab is a set of statuses, so "To pack and ship" shows orders that are paid or being prepared. */
const GROUPS = [
  { id: "all", label: "All", statuses: [] as OrderStatus[] },
  { id: "to_ship", label: "To pack and ship", statuses: ["paid", "processing"] as OrderStatus[] },
  { id: "pending", label: "Awaiting payment", statuses: ["pending"] as OrderStatus[] },
  { id: "shipped", label: "Shipped", statuses: ["shipped"] as OrderStatus[] },
  { id: "delivered", label: "Delivered", statuses: ["delivered"] as OrderStatus[] },
  { id: "closed", label: "Cancelled and refunded", statuses: ["cancelled", "refunded"] as OrderStatus[] },
];

export default function AdminOrders() {
  const [group, setGroup] = useState("all");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page<OrderListItem> | null>(null);
  const [counts, setCounts] = useState<Record<string, number> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("status");
    if (initial && GROUPS.some((g) => g.id === initial)) setGroup(initial);
  }, []);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    GROUPS.find((g) => g.id === group)?.statuses.forEach((s) => params.append("status", s));
    if (q) params.set("q", q);
    setLoading(true);
    try {
      const [list, c] = await Promise.all([
        apiFetch<Page<OrderListItem>>(`/orders?${params}`),
        apiFetch<{ counts: Record<string, number> }>("/orders/counts"),
      ]);
      setData(list);
      setCounts(c.counts);
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load orders");
    } finally {
      setLoading(false);
    }
  }, [page, group, q]);

  useEffect(() => {
    void load();
  }, [load]);

  const tabs = useMemo(
    () =>
      GROUPS.map((g) => ({
        id: g.id,
        label: g.label,
        count: counts ? (g.statuses.length === 0 ? Object.values(counts).reduce((a, b) => a + b, 0) : g.statuses.reduce((n, s) => n + (counts[s] ?? 0), 0)) : undefined,
      })),
    [counts],
  );

  const columns: Column<OrderListItem>[] = [
    {
      key: "order",
      header: "Order",
      cell: (o) => (
        <div>
          <Link href={`/admin/orders/${o.number}`} className="font-medium text-accent hover:underline">
            {o.number}
          </Link>
          <span className="block text-xs text-muted">{fmtDateTime(o.placed_at)}</span>
          <span className="mt-1 block md:hidden">
            <Pill tone={STATUS_TONE[o.status]}>{STATUS_LABEL[o.status]}</Pill>
          </span>
        </div>
      ),
    },
    {
      key: "customer",
      header: "Customer",
      hide: "sm",
      cell: (o) => (
        <div className="min-w-0">
          <p className="truncate font-medium">{o.customer || "—"}</p>
          <p className="truncate text-xs text-muted">{o.email}</p>
        </div>
      ),
    },
    { key: "status", header: "Status", hide: "md", cell: (o) => <Pill tone={STATUS_TONE[o.status]}>{STATUS_LABEL[o.status]}</Pill> },
    {
      key: "payment",
      header: "Payment",
      hide: "lg",
      cell: (o) => (
        <span className="text-muted">
          {o.payment_provider ? PROVIDER_LABEL[o.payment_provider] : "—"}
          {o.coupon_code && <span className="block text-xs">Code {o.coupon_code}</span>}
        </span>
      ),
    },
    {
      key: "total",
      header: "Total",
      align: "right",
      cell: (o) => (
        <span className="num">
          {formatPrice(o.grand_total, "USD")}
          {o.refunded_total > 0 && <span className="block text-xs text-muted">−{formatPrice(o.refunded_total, "USD")} refunded</span>}
          <span className="block text-xs text-muted">{o.item_count} {o.item_count === 1 ? "item" : "items"}</span>
        </span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title="Orders" description="Pack and ship paid orders, keep an eye on payments, and help customers when something goes wrong." />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      <Panel>
        <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 px-2 pt-1">
          <Tabs
            label="Filter orders"
            tabs={tabs}
            value={group}
            onChange={(id) => {
              setPage(1);
              setGroup(id);
            }}
            className="border-b-0"
          />
          <form
            role="search"
            className="flex items-center gap-2 pb-2 pr-2"
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              setQ(String(new FormData(e.currentTarget).get("q") || "").trim());
            }}
          >
            <label htmlFor="order-q" className="sr-only">
              Search orders
            </label>
            <div className="relative">
              <Icon name="search" className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
              <input
                id="order-q"
                name="q"
                type="search"
                placeholder="Order number, name or email"
                className="h-8 w-64 rounded-[var(--radius-control)] border border-line bg-surface pl-8 pr-2 text-sm placeholder:text-muted/70 focus-visible:border-accent"
              />
            </div>
            <Button type="submit" variant="secondary" size="sm" className="h-8">
              Search
            </Button>
          </form>
        </div>
        <div className="border-t border-line">
          <DataTable
            caption="Orders"
            columns={columns}
            rows={data ? data.items : null}
            rowKey={(o) => o.number}
            loading={loading}
            empty={q ? "No order matches that search." : group === "all" ? "No orders yet. They will appear here the moment someone checks out." : "Nothing in this group."}
          />
          {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />}
        </div>
      </Panel>
    </div>
  );
}
