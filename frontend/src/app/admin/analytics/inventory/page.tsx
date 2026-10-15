"use client";

import Link from "next/link";
import { useState } from "react";
import { Empty, Loading, ReportHeader, useReport } from "@/components/admin/analytics/common";
import { fmtInt, money } from "@/components/admin/charts/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { Pagination } from "@/components/admin/ui/Pagination";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";
import { Tabs } from "@/components/admin/ui/Tabs";

type Status = "out" | "low" | "dead" | "healthy" | "untracked";
interface Item {
  id: number;
  /** The product page (the parent, for a variant). */
  product_id: number;
  title: string;
  sku: string | null;
  stock: number | null;
  status: Status;
  sold_30d: number;
  sold_90d: number;
  days_of_cover: number | null;
  waiting: number;
  value_at_cost: number | null;
  reorder: number;
}
interface InventoryReport {
  summary: Record<Status, number> & { items: number; tracked: number; units: number; value_at_cost: number; value_at_retail: number; costed_items: number; waiting: number };
  items: Item[];
  waitlist: { id: number; product_id: number; title: string; requests: number }[];
  rules: { low: string; dead: string; reorder: string };
}

const STATUS: Record<Status, { label: string; tone: Tone }> = {
  out: { label: "Out of stock", tone: "danger" },
  low: { label: "Running low", tone: "warning" },
  dead: { label: "Not selling", tone: "neutral" },
  healthy: { label: "Healthy", tone: "success" },
  untracked: { label: "Not tracked", tone: "info" },
};
type Filter = "attention" | Status | "all";
const PAGE_SIZE = 25;

export default function InventoryReportPage() {
  const { data, error } = useReport<InventoryReport>("inventory", false);
  const [filter, setFilter] = useState<Filter>("attention");
  const [page, setPage] = useState(1);
  const s = data?.summary;
  const rows = (data?.items ?? []).filter((i) => filter === "all" || (filter === "attention" ? i.status === "out" || i.status === "low" : i.status === filter));

  const columns: Column<Item>[] = [
    {
      key: "product",
      header: "Product",
      cell: (i) => (
        <span className="block min-w-0">
          <Link href={`/admin/products/${i.product_id}`} className="block max-w-[18rem] truncate font-medium hover:underline">
            {i.title}
          </Link>
          <span className="flex items-center gap-2 text-xs text-muted">
            <Pill tone={STATUS[i.status].tone}>{STATUS[i.status].label}</Pill>
            {i.sku}
          </span>
        </span>
      ),
    },
    { key: "stock", header: "In stock", align: "right", cell: (i) => <span className="num">{i.stock ?? "—"}</span> },
    { key: "sold", header: "Sold (30 d)", align: "right", hide: "md", cell: (i) => <span className="num">{fmtInt(i.sold_30d)}</span> },
    { key: "cover", header: "Days left", align: "right", hide: "md", cell: (i) => <span className="num">{i.days_of_cover != null ? Math.round(i.days_of_cover) : "—"}</span> },
    { key: "waiting", header: "Waiting", align: "right", hide: "lg", cell: (i) => <span className="num">{i.waiting || "—"}</span> },
    { key: "reorder", header: "Reorder", align: "right", cell: (i) => <span className={i.reorder > 0 ? "num font-semibold" : "num text-muted"}>{i.reorder > 0 ? fmtInt(i.reorder) : "—"}</span> },
  ];

  return (
    <div>
      <ReportHeader
        title="Inventory"
        description="What to restock, what's stuck on the shelf, and what shoppers are waiting for. Always as of now."
        exportKind="inventory"
        error={error}
      />
      <MetricStrip
        items={[
          { label: "Out of stock", value: s ? fmtInt(s.out) : "—" },
          { label: "Running low", value: s ? fmtInt(s.low) : "—" },
          { label: "Not selling", value: s ? fmtInt(s.dead) : "—", hint: "In stock, no sale in 90 days" },
          { label: "Units in stock", value: s ? fmtInt(s.units) : "—", hint: s ? `${s.tracked} of ${s.items} items track stock` : undefined },
          {
            label: "Stock value",
            value: s ? money(s.value_at_cost) : "—",
            hint: s ? `At cost (${s.costed_items} items have a cost price); ${money(s.value_at_retail)} at retail` : undefined,
          },
        ]}
      />

      <Panel className="mt-6">
        <div className="px-4 pt-3">
          <Tabs<Filter>
            label="Show"
            value={filter}
            onChange={(f) => {
              setFilter(f);
              setPage(1);
            }}
            tabs={[
              { id: "attention", label: "Needs restocking", count: s ? s.out + s.low : undefined },
              { id: "dead", label: "Not selling", count: s?.dead },
              { id: "healthy", label: "Healthy", count: s?.healthy },
              { id: "untracked", label: "Not tracked", count: s?.untracked },
              { id: "all", label: "All", count: s?.items },
            ]}
          />
        </div>
        <DataTable
          columns={columns}
          rows={data ? rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) : null}
          rowKey={(i) => i.id}
          caption="Stock levels"
          empty={filter === "attention" ? "Nothing needs restocking." : "No items here."}
        />
        {data && <Pagination page={page} pageSize={PAGE_SIZE} total={rows.length} onPage={setPage} className="px-4 py-3" />}
        {data && (
          <dl className="grid gap-1 border-t border-line px-5 py-3 text-xs text-muted sm:grid-cols-3">
            <div>
              <dt className="inline font-medium text-ink">Running low: </dt>
              <dd className="inline">{data.rules.low}</dd>
            </div>
            <div>
              <dt className="inline font-medium text-ink">Not selling: </dt>
              <dd className="inline">{data.rules.dead}</dd>
            </div>
            <div>
              <dt className="inline font-medium text-ink">Reorder: </dt>
              <dd className="inline">{data.rules.reorder}</dd>
            </div>
          </dl>
        )}
      </Panel>

      <Panel className="mt-6">
        <PanelHeader title="Waiting for restock" description="Shoppers who asked to be emailed when an item is back. They're told automatically when you add stock." />
        <PanelBody>
          {!data ? (
            <Loading />
          ) : data.waitlist.length === 0 ? (
            <Empty>Nobody is waiting.</Empty>
          ) : (
            <ul className="divide-y divide-line text-sm">
              {data.waitlist.map((w) => (
                <li key={w.id} className="flex justify-between gap-3 py-2.5">
                  <Link href={`/admin/products/${w.product_id}`} className="min-w-0 truncate font-medium hover:underline">
                    {w.title}
                  </Link>
                  <span className="num shrink-0 text-muted">{w.requests} waiting</span>
                </li>
              ))}
            </ul>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
