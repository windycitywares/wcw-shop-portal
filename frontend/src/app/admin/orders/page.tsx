"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { downloadFile } from "@/components/admin/download";
import { dateTime, money } from "@/components/admin/charts/format";
import { PAYMENT_LABEL, PROVIDER_LABEL, type OrderList, type OrderListItem } from "@/components/admin/orders/types";
import { CHANNEL_LABEL, ORDER_STATUS } from "@/components/admin/reports";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

const PAGE_SIZE = 25;
type TabId = "all" | "action" | "pending" | "paid" | "processing" | "shipped" | "delivered" | "cancelled" | "refunded";
const TABS: { id: TabId; label: string }[] = [
  { id: "all", label: "All" },
  { id: "action", label: "Needs action" },
  { id: "pending", label: "Awaiting payment" },
  { id: "paid", label: "To ship" },
  { id: "processing", label: "Preparing" },
  { id: "shipped", label: "Shipped" },
  { id: "delivered", label: "Delivered" },
  { id: "cancelled", label: "Cancelled" },
  { id: "refunded", label: "Refunded" },
];
const SORTS = [
  { id: "newest", label: "Newest first" },
  { id: "oldest", label: "Oldest first" },
  { id: "total_desc", label: "Largest total" },
  { id: "total_asc", label: "Smallest total" },
];

export default function AdminOrders() {
  const [tab, setTab] = useState<TabId>("all");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<OrderList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Links from the dashboard: /admin/orders?status=paid, ?payment=refunded, ?q=WCW-1042
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const status = p.get("status");
    if (status && TABS.some((t) => t.id === status)) setTab(status as TabId);
    if (p.get("payment") === "refunded") setTab("refunded");
    if (p.get("q")) {
      setQ(p.get("q") ?? "");
      setDraft(p.get("q") ?? "");
    }
  }, []);

  const params = useCallback(() => {
    const p = new URLSearchParams({ sort, page: String(page), page_size: String(PAGE_SIZE) });
    if (q) p.set("q", q);
    if (tab === "action") p.set("needs_action", "true");
    else if (tab !== "all") p.set("status", tab);
    return p;
  }, [q, sort, page, tab]);

  useEffect(() => {
    setLoading(true);
    apiFetch<OrderList>(`/admin/orders?${params()}`)
      .then((d) => {
        setData(d);
        setError("");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Couldn't load orders"))
      .finally(() => setLoading(false));
  }, [params]);

  const columns: Column<OrderListItem>[] = [
    {
      key: "order",
      header: "Order",
      cell: (o) => (
        <div>
          <Link href={`/admin/orders/${o.id}`} className="num font-medium hover:underline">
            {o.number}
          </Link>
          <span className="block text-xs text-muted">{o.placed_at ? dateTime(o.placed_at) : "—"}</span>
        </div>
      ),
    },
    {
      key: "customer",
      header: "Customer",
      cell: (o) => (
        <div className="min-w-0">
          <span className="block max-w-[16rem] truncate">{o.customer_name || o.email}</span>
          <span className="block max-w-[16rem] truncate text-xs text-muted">{o.customer_name ? o.email : `${o.item_count} item${o.item_count === 1 ? "" : "s"}`}</span>
        </div>
      ),
    },
    {
      key: "payment",
      header: "Payment",
      hide: "md",
      cell: (o) => (
        <div className="text-sm">
          <span className="block">{PAYMENT_LABEL[o.payment_status] ?? o.payment_status}</span>
          <span className="block text-xs text-muted">
            {PROVIDER_LABEL[o.payment_provider ?? ""] ?? o.payment_provider}
            {o.coupon_code ? ` · ${o.coupon_code}` : ""}
          </span>
        </div>
      ),
    },
    { key: "channel", header: "Came from", hide: "lg", cell: (o) => <span className="text-sm text-muted">{o.channel ? CHANNEL_LABEL[o.channel] ?? o.channel : "—"}</span> },
    {
      key: "status",
      header: "Status",
      cell: (o) => {
        const s = ORDER_STATUS[o.status] ?? { label: o.status, tone: "neutral" as const };
        return <Pill tone={s.tone}>{s.label}</Pill>;
      },
    },
    {
      key: "total",
      header: "Total",
      align: "right",
      cell: (o) => (
        <span className="num">
          {money(o.grand_total)}
          {o.refunded_total > 0 && <span className="block text-xs text-muted">−{money(o.refunded_total)} refunded</span>}
        </span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Orders"
        description="Every sale in one list. Find an order, take payment, ship it, refund or cancel it. Totals over time are in Sales report."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => downloadFile(`/admin/orders/export.csv?${params()}`, "wcw-orders.csv").catch((e) => setError(e.message))}
          >
            Export CSV
          </Button>
        }
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      <MetricStrip
        className="mb-6"
        items={[
          { label: "Orders", value: data ? String(data.stats.orders) : "—", hint: "Matching the filters below" },
          { label: "Revenue", value: data ? money(data.stats.revenue) : "—", hint: "Paid orders, minus refunds" },
          { label: "Need action", value: data ? String(data.stats.open_orders) : "—", hint: "Unpaid, or paid and not shipped yet" },
        ]}
      />
      <Panel>
        <div className="flex flex-wrap items-end gap-3 border-b border-line px-4 pt-3">
          <Tabs
            tabs={TABS}
            value={tab}
            onChange={(id) => {
              setTab(id);
              setPage(1);
            }}
            label="Order status"
            className="min-w-0 flex-1"
          />
        </div>
        <form
          className="flex flex-wrap items-center gap-3 px-4 py-3"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(draft.trim());
            setPage(1);
          }}
        >
          <label htmlFor="order-search" className="sr-only">
            Search orders
          </label>
          <Input
            id="order-search"
            type="search"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Order number, email or name"
            className="h-9 max-w-xs"
          />
          <Button type="submit" variant="secondary" size="sm">
            Search
          </Button>
          <label className="ml-auto flex items-center gap-2 text-sm">
            <span className="text-muted">Sort</span>
            <select
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                setPage(1);
              }}
              className="h-9 rounded-lg border border-line bg-surface px-2 text-sm"
            >
              {SORTS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </form>
        <DataTable
          columns={columns}
          rows={data?.items ?? null}
          rowKey={(o) => o.id}
          caption="Orders"
          loading={loading}
          empty={q || tab !== "all" ? "No orders match. Try another search or tab." : "No orders yet. They'll appear here as soon as the first one is placed."}
        />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} className="px-4 py-3" />}
      </Panel>
    </div>
  );
}
