"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/client-api";
import { ShopTabs } from "@/components/admin/ShopTabs";
import { Stat, Thumb } from "@/components/admin/etsy/ui";
import { SupplierFilter, useSupplierFilter } from "@/components/admin/etsy/SupplierFilter";
import { dateTime, fmtInt, money } from "@/components/admin/charts/format";
import { ATTENTION_LABEL, EXCEPTIONS, MAIN_PATH, STATUS_LABEL, STATUS_TONE, type OrderSummary } from "@/components/admin/etsy/orders";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Page {
  items: OrderSummary[];
  total: number;
  counts: Record<string, number>;
  attention: number;
}
type View = "attention" | "open" | "all";
const PAGE_SIZE = 25;
const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");
const m = (v: string | number | null | undefined) => (v == null ? "—" : money(Number(v), { cents: true }));

export default function EtsyOrders() {
  const [view, setView] = useState<View>("open");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [supplier, setSupplier] = useSupplierFilter();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [applied, setApplied] = useState({ q: "", from: "", to: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
      if (status) p.set("status", status);
      else if (view === "open") p.set("status", "open");
      if (view === "attention") p.set("attention", "true");
      if (applied.q) p.set("q", applied.q);
      if (supplier) p.set("supplier", supplier);
      if (applied.from) p.set("date_from", applied.from);
      if (applied.to) p.set("date_to", applied.to);
      setData(await apiFetch<Page>(`/admin/etsy/orders?${p}`));
      setError(null);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [page, view, status, applied, supplier]);
  useEffect(() => {
    void load();
  }, [load]);

  const openCount = data ? ["new", "purchased", "shipped", "issue", "replacement", "return_requested"].reduce((n, s) => n + (data.counts[s] ?? 0), 0) : undefined;
  const columns: Column<OrderSummary>[] = [
    {
      key: "order",
      header: "Order",
      cell: (o) => (
        <Link href={`/admin/etsy/orders/${o.id}`} className="flex min-w-0 items-center gap-3 font-medium text-accent underline-offset-2 hover:underline">
          <Thumb src={o.items[0]?.image} size="sm" />
          <span className="min-w-0">
            #{o.etsy_receipt_id}
            <span className="block truncate text-xs font-normal text-muted">{o.buyer_name ?? "Buyer"} · {dateTime(o.ordered_at)}</span>
          </span>
        </Link>
      ),
    },
    {
      key: "items",
      header: "Items",
      hide: "md",
      cell: (o) => <span className="line-clamp-2 max-w-64" title={o.items.map((i) => `${i.quantity}× ${i.title}`).join(", ")}>{o.items.map((i) => `${i.quantity}× ${i.title.split(" - ")[0]}`).join(", ")}</span>,
    },
    { key: "status", header: "Status", cell: (o) => <Pill tone={STATUS_TONE[o.status] ?? "neutral"}>{STATUS_LABEL[o.status] ?? o.status}</Pill> },
    { key: "revenue", header: "Revenue", align: "right", hide: "sm", cell: (o) => m(o.profit.revenue) },
    {
      key: "profit",
      header: "Profit",
      align: "right",
      cell: (o) => (
        <span className={Number(o.profit.net_profit) < 0 ? "font-medium text-danger" : undefined}>
          {o.profit.missing.includes("purchase_cost") ? <span className="text-muted">Cost missing</span> : m(o.profit.net_profit)}
        </span>
      ),
    },
    {
      key: "attention",
      header: <span className="sr-only">Needs attention</span>,
      cell: (o) =>
        o.attention.length ? (
          <span className="inline-flex items-center gap-1 text-xs text-danger" title={o.attention.map((a) => ATTENTION_LABEL[a] ?? a).join(" · ")}>
            <Icon name="alert" className="size-4" />
            <span className="hidden lg:inline">{ATTENTION_LABEL[o.attention[0]] ?? o.attention[0]}{o.attention.length > 1 ? ` +${o.attention.length - 1}` : ""}</span>
            <span className="sr-only lg:hidden">{o.attention.map((a) => ATTENTION_LABEL[a] ?? a).join(", ")}</span>
          </span>
        ) : null,
    },
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader
        title="Etsy orders"
        description="Paid Etsy orders arrive here on their own within minutes. Enter what you paid and how you shipped; profit follows."
        actions={<Link href="/admin/settings?tab=external_shops&shop=etsy" className="text-sm font-medium text-accent underline">Etsy connection</Link>}
      />
      <ShopTabs shop="etsy" />
      {error ? <Alert tone="danger">{error}</Alert> : null}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Needs attention" value={data ? fmtInt(data.attention) : "—"} sub="Late, unpurchased or missing a cost" tone={data?.attention ? "danger" : undefined}
          active={view === "attention" && !status} onClick={() => { setView("attention"); setStatus(""); setPage(1); }} />
        <Stat label="To purchase" value={data ? fmtInt(data.counts.new ?? 0) : "—"} sub="New, paid on Etsy" tone={data?.counts.new ? "warning" : undefined}
          active={status === "new"} onClick={() => { setView("all"); setStatus("new"); setPage(1); }} />
        <Stat label="To ship" value={data ? fmtInt(data.counts.purchased ?? 0) : "—"} sub="Purchased, not shipped"
          active={status === "purchased"} onClick={() => { setView("all"); setStatus("purchased"); setPage(1); }} />
        <Stat label="Shipped" value={data ? fmtInt(data.counts.shipped ?? 0) : "—"} sub="Delivery not confirmed yet"
          active={status === "shipped"} onClick={() => { setView("all"); setStatus("shipped"); setPage(1); }} />
      </div>
      <Panel>
        <Tabs<View>
          label="Which orders"
          className="px-4"
          tabs={[
            { id: "attention", label: "Needs attention", count: data?.attention },
            { id: "open", label: "Open", count: openCount },
            { id: "all", label: "All" },
          ]}
          value={view}
          onChange={(v) => {
            setView(v);
            setStatus("");
            setPage(1);
          }}
        />
        <form
          className="grid grid-cols-[minmax(0,1fr)] gap-3 border-b border-line p-4 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr_1fr_auto] lg:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setApplied({ q: q.trim(), from, to });
          }}
        >
          <Field label="Search">{(p) => <Input {...p} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Order #, buyer, item, SKU, tracking" />}</Field>
          <Field label="Status">
            {(p) => (
              <Select {...p} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
                <option value="">{view === "open" ? "Any open" : "Any"}</option>
                <optgroup label="Main path">{MAIN_PATH.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}{data ? ` (${data.counts[s] ?? 0})` : ""}</option>)}</optgroup>
                <optgroup label="Exceptions">{EXCEPTIONS.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}{data ? ` (${data.counts[s] ?? 0})` : ""}</option>)}</optgroup>
              </Select>
            )}
          </Field>
          <SupplierFilter value={supplier} onChange={(v) => { setSupplier(v); setPage(1); }} className="" />
          <Field label="From">{(p) => <Input {...p} type="date" value={from} onChange={(e) => setFrom(e.target.value)} />}</Field>
          <Field label="To">{(p) => <Input {...p} type="date" value={to} onChange={(e) => setTo(e.target.value)} />}</Field>
          <Button type="submit">Filter</Button>
        </form>
        <DataTable
          columns={columns}
          rows={data ? data.items : null}
          rowKey={(o) => o.id}
          caption="Etsy orders"
          loading={loading}
          empty={view === "attention" ? "Nothing needs attention." : "No Etsy orders match. New paid orders appear within a few minutes."}
        />
        {data ? <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} /> : null}
      </Panel>
    </div>
  );
}
