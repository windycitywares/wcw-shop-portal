"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { money, pct, timeAgo } from "@/components/admin/charts/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { DateRangePicker } from "@/components/admin/ui/DateRangePicker";
import { rangeParams } from "@/components/admin/ui/dateRange";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { useDateRange } from "@/components/admin/ui/useDateRange";
import { Alert } from "@/components/ui/misc";

interface CartRow {
  id: number;
  status: "active" | "abandoned" | "converted" | "recovered";
  items: { product_id: number; title: string; quantity: number }[];
  item_count: number;
  subtotal: number;
  coupon_code: string | null;
  email: string | null;
  reminders_sent: number;
  checkout_started: boolean;
  created_at: string;
  last_activity_at: string;
  order_number: string | null;
}

interface CartList {
  items: CartRow[];
  total: number;
  summary: {
    started: number;
    converted: number;
    abandoned: number;
    active: number;
    abandoned_value: number;
    abandonment_rate: number | null;
    reachable: number;
    reminders_sent: number;
    recovered: number;
    recovered_value: number;
    reached_checkout: number;
  };
}

type Tab = "all" | "abandoned" | "active" | "converted" | "recovered";
const TABS: { id: Tab; label: string }[] = [
  { id: "abandoned", label: "Abandoned" },
  { id: "recovered", label: "Recovered" },
  { id: "converted", label: "Ordered" },
  { id: "active", label: "Shopping now" },
  { id: "all", label: "All" },
];
const STATUS: Record<CartRow["status"], { label: string; tone: Tone }> = {
  abandoned: { label: "Abandoned", tone: "warning" },
  active: { label: "Shopping now", tone: "info" },
  converted: { label: "Ordered", tone: "success" },
  recovered: { label: "Recovered by reminder", tone: "accent" },
};
const PAGE_SIZE = 25;

export default function AdminCarts() {
  const [range, setRange] = useDateRange("30d");
  const [tab, setTab] = useState<Tab>("abandoned");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<CartList | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const extra: Record<string, string> = { page: String(page), page_size: String(PAGE_SIZE) };
    if (tab !== "all") extra.status = tab;
    apiFetch<CartList>(`/admin/carts?${rangeParams(range, extra)}`).then(
      (d) => {
        setData(d);
        setError("");
      },
      (e) => setError(e.message),
    );
  }, [range, tab, page]);

  const s = data?.summary;
  const columns: Column<CartRow>[] = [
    {
      key: "items",
      header: "Cart",
      cell: (c) => (
        <div className="min-w-0 text-sm">
          <span className="block max-w-[22rem] truncate">{c.items.map((i) => (i.quantity > 1 ? `${i.title} × ${i.quantity}` : i.title)).join(", ")}</span>
          <span className="block text-xs text-muted">
            {c.email ?? "No email (reminders not requested)"}
            {c.coupon_code ? ` · ${c.coupon_code}` : ""}
            {c.checkout_started ? " · reached checkout" : ""}
          </span>
        </div>
      ),
    },
    { key: "value", header: "Value", align: "right", cell: (c) => <span className="num">{money(c.subtotal)}</span> },
    { key: "reminders", header: "Reminders", align: "right", hide: "md", cell: (c) => <span className="num text-sm">{c.reminders_sent}</span> },
    { key: "when", header: "Last activity", hide: "lg", cell: (c) => <span className="text-sm text-muted">{timeAgo(c.last_activity_at)}</span> },
    {
      key: "status",
      header: "Status",
      cell: (c) => (
        <span className="text-sm">
          <Pill tone={STATUS[c.status].tone}>{STATUS[c.status].label}</Pill>
          {c.order_number && (
            <Link href={`/admin/orders?q=${encodeURIComponent(c.order_number)}`} className="num ml-2 text-accent underline underline-offset-4">
              {c.order_number}
            </Link>
          )}
        </span>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Abandoned carts"
        description="Carts people filled but didn't order. Shoppers who ask for it at checkout get up to two gentle reminders (Settings → Cart reminders)."
        actions={<DateRangePicker value={range} onChange={setRange} />}
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
      <MetricStrip
        className="mb-6"
        items={[
          { label: "Carts started", value: s ? String(s.started) : "—" },
          { label: "Abandoned", value: s ? String(s.abandoned) : "—", hint: s ? `${money(s.abandoned_value)} left behind` : undefined },
          { label: "Abandonment rate", value: s?.abandonment_rate != null ? pct(s.abandonment_rate) : "—", hint: "Of carts that are no longer active" },
          { label: "Can be reminded", value: s ? String(s.reachable) : "—", hint: "Asked for a reminder" },
          { label: "Recovered", value: s ? String(s.recovered) : "—", hint: s ? `${money(s.recovered_value)} after a reminder` : undefined },
        ]}
      />
      <Panel>
        <div className="border-b border-line px-4 pt-3">
          <Tabs
            tabs={TABS}
            value={tab}
            onChange={(id) => {
              setTab(id);
              setPage(1);
            }}
            label="Cart status"
          />
        </div>
        <DataTable columns={columns} rows={data?.items ?? null} rowKey={(c) => c.id} caption="Carts" empty="No carts in this period." />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} className="px-4 py-3" />}
      </Panel>
    </div>
  );
}
