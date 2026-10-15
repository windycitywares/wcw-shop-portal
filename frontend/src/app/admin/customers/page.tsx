"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { downloadFile } from "@/components/admin/download";
import { dateTime, money, timeAgo } from "@/components/admin/charts/format";
import { ORDER_STATUS } from "@/components/admin/reports";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Modal } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Customer {
  email: string;
  name: string | null;
  orders: number;
  revenue: number;
  average_order: number;
  first_order_at: string;
  last_order_at: string;
  segment: string;
  subscribed: boolean;
  has_account: boolean;
}

interface Segment {
  key: string;
  label: string;
  help: string;
  customers: number;
  revenue: number;
}

interface CustomerList {
  items: Customer[];
  total: number;
  segments: Segment[];
  total_customers: number;
  subscribers_without_orders: number;
}

interface CustomerDetail {
  summary: Customer;
  refunded: number;
  orders: { id: number; number: string; status: string; payment_status: string; grand_total: number; refunded_total: number; coupon_code: string | null; placed_at: string | null }[];
  coupons: { code: string; kind: string; value: number; status: string; source: string; expires_at: string | null }[];
  subscription: { status: string; source: string; since: string } | null;
  reviews: number;
  account_role: string | null;
}

const SEGMENT_TONE: Record<string, Tone> = {
  vip: "accent",
  loyal: "success",
  active: "success",
  new: "info",
  needs_nudge: "warning",
  at_risk: "danger",
  lapsed: "neutral",
};
const SORTS = [
  { id: "revenue", label: "Most spent" },
  { id: "orders", label: "Most orders" },
  { id: "recent", label: "Ordered most recently" },
  { id: "oldest", label: "Longest since last order" },
  { id: "name", label: "Name" },
];
const PAGE_SIZE = 25;

export default function AdminCustomers() {
  const [segment, setSegment] = useState("");
  const [sort, setSort] = useState("revenue");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<CustomerList | null>(null);
  const [detail, setDetail] = useState<CustomerDetail | null>(null);
  const [error, setError] = useState("");

  const query = useCallback(() => {
    const p = new URLSearchParams({ sort, page: String(page), page_size: String(PAGE_SIZE) });
    if (q) p.set("q", q);
    if (segment) p.set("segment", segment);
    return p;
  }, [q, sort, page, segment]);

  useEffect(() => {
    apiFetch<CustomerList>(`/admin/customers?${query()}`).then(
      (d) => {
        setData(d);
        setError("");
      },
      (e) => setError(e.message),
    );
  }, [query]);

  const label = (key: string) => data?.segments.find((s) => s.key === key)?.label ?? key;

  const columns: Column<Customer>[] = [
    {
      key: "who",
      header: "Customer",
      cell: (c) => (
        <div className="min-w-0">
          <button
            type="button"
            className="block max-w-[18rem] truncate text-left font-medium hover:underline"
            onClick={() => apiFetch<CustomerDetail>(`/admin/customers/detail?email=${encodeURIComponent(c.email)}`).then(setDetail, (e) => setError(e.message))}
          >
            {c.name || c.email}
          </button>
          <span className="block max-w-[18rem] truncate text-xs text-muted">
            {c.name ? c.email : ""}
            {c.has_account ? " · account" : ""}
            {c.subscribed ? " · subscribed" : ""}
          </span>
        </div>
      ),
    },
    { key: "segment", header: "Group", cell: (c) => <Pill tone={SEGMENT_TONE[c.segment] ?? "neutral"}>{label(c.segment)}</Pill> },
    { key: "orders", header: "Orders", align: "right", cell: (c) => <span className="num">{c.orders}</span> },
    { key: "revenue", header: "Spent", align: "right", cell: (c) => <span className="num">{money(c.revenue)}</span> },
    { key: "aov", header: "Average order", align: "right", hide: "md", cell: (c) => <span className="num">{money(c.average_order)}</span> },
    { key: "last", header: "Last order", hide: "lg", cell: (c) => <span className="text-sm text-muted">{timeAgo(c.last_order_at)}</span> },
  ];

  return (
    <div>
      <PageHeader
        title="Customers"
        description="Everyone who has paid for an order, grouped by how recently and how often they buy."
        actions={
          <Button size="sm" variant="secondary" onClick={() => downloadFile(`/admin/customers/export.csv?${query()}`, "wcw-customers.csv").catch((e) => setError(e.message))}>
            Export CSV
          </Button>
        }
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}

      <ul className="mb-6 grid grid-cols-[minmax(0,1fr)] gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Customer groups">
        {(data?.segments ?? []).map((s) => (
          <li key={s.key}>
            <button
              type="button"
              aria-pressed={segment === s.key}
              onClick={() => {
                setSegment(segment === s.key ? "" : s.key);
                setPage(1);
              }}
              className={`h-full w-full rounded-[var(--radius-card)] border bg-surface p-4 text-left hover:border-ink/30 ${segment === s.key ? "border-accent ring-1 ring-accent" : "border-line"}`}
            >
              <span className="flex items-center justify-between gap-2">
                <Pill tone={SEGMENT_TONE[s.key] ?? "neutral"}>{s.label}</Pill>
                <span className="num text-lg font-medium">{s.customers}</span>
              </span>
              <span className="mt-2 block text-xs text-muted">{s.help}</span>
              <span className="num mt-1 block text-sm">{money(s.revenue)} spent</span>
            </button>
          </li>
        ))}
      </ul>
      {data && (
        <p className="mb-4 text-sm text-muted">
          {data.total_customers} customers in total. {data.subscribers_without_orders} newsletter subscribers haven't bought yet; reach them with an email campaign.
        </p>
      )}

      <Panel>
        <form
          className="flex flex-wrap items-center gap-3 px-4 py-3"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(draft.trim());
            setPage(1);
          }}
        >
          <label htmlFor="customer-search" className="sr-only">
            Search customers
          </label>
          <Input id="customer-search" type="search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Name or email" className="h-9 max-w-xs" />
          <Button type="submit" size="sm" variant="secondary">
            Search
          </Button>
          {segment && (
            <Button size="sm" variant="ghost" onClick={() => setSegment("")}>
              Show all groups
            </Button>
          )}
          <label className="ml-auto flex items-center gap-2 text-sm">
            <span className="text-muted">Sort</span>
            <select className="h-9 rounded-lg border border-line bg-surface px-2" value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }}>
              {SORTS.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </form>
        <DataTable columns={columns} rows={data?.items ?? null} rowKey={(c) => c.email} caption="Customers" empty="No customers yet. Everyone who pays for an order appears here." />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} className="px-4 py-3" />}
      </Panel>

      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail?.summary.name || detail?.summary.email || ""} description={detail?.summary.email} size="lg">
        {detail && (
          <div className="space-y-5 text-sm">
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                ["Orders", String(detail.summary.orders)],
                ["Spent", money(detail.summary.revenue)],
                ["Average order", money(detail.summary.average_order)],
                ["Refunded", money(detail.refunded)],
              ].map(([k, v]) => (
                <div key={k} className="rounded-lg bg-canvas px-3 py-2">
                  <dt className="text-xs text-muted">{k}</dt>
                  <dd className="num font-medium">{v}</dd>
                </div>
              ))}
            </dl>
            <p className="text-muted">
              Group: <span className="text-ink">{label(detail.summary.segment)}</span> · first order {dateTime(detail.summary.first_order_at)} ·{" "}
              {detail.account_role ? "has an account" : "guest checkout"} · {detail.reviews} review{detail.reviews === 1 ? "" : "s"} ·{" "}
              {detail.subscription ? (detail.subscription.status === "subscribed" ? "subscribed to news" : "unsubscribed from news") : "not on the email list"}
            </p>
            <div>
              <h3 className="mb-2 font-medium">Orders</h3>
              <ul className="divide-y divide-line rounded-lg border border-line">
                {detail.orders.map((o) => {
                  const s = ORDER_STATUS[o.status] ?? { label: o.status, tone: "neutral" as const };
                  return (
                    <li key={o.id} className="flex items-center justify-between gap-3 px-3 py-2">
                      <span>
                        <Link href={`/admin/orders/${o.id}`} className="num font-medium text-accent underline underline-offset-4">
                          {o.number}
                        </Link>
                        <span className="block text-xs text-muted">
                          {o.placed_at ? dateTime(o.placed_at) : ""}
                          {o.coupon_code ? ` · ${o.coupon_code}` : ""}
                        </span>
                      </span>
                      <span className="flex items-center gap-3">
                        <Pill tone={s.tone}>{s.label}</Pill>
                        <span className="num">{money(o.grand_total)}</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
            {detail.coupons.length > 0 && (
              <div>
                <h3 className="mb-2 font-medium">Their personal codes</h3>
                <ul className="space-y-1">
                  {detail.coupons.map((c) => (
                    <li key={c.code}>
                      <span className="font-mono">{c.code}</span> · {c.kind === "percent" ? `${c.value}% off` : c.kind === "fixed" ? `${money(c.value)} off` : "free shipping"} · {c.status}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
