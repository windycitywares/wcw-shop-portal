"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/client-api";
import { KpiStrip, bucketFormat, type RangeInfo } from "@/components/admin/analytics/common";
import { BarList } from "@/components/admin/charts/BarList";
import { ChartFrame } from "@/components/admin/charts/ChartFrame";
import { ColumnChart } from "@/components/admin/charts/ColumnChart";
import { LineChart, lineTable } from "@/components/admin/charts/LineChart";
import { fmtInt, money, pct } from "@/components/admin/charts/format";
import { STATUS_LABEL } from "@/components/admin/etsy/orders";
import type { Kpi } from "@/components/admin/reports";
import { ShopTabs } from "@/components/admin/ShopTabs";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { DateRangePicker } from "@/components/admin/ui/DateRangePicker";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { useDateRange } from "@/components/admin/ui/useDateRange";
import { Button } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Summary {
  orders: number;
  cancelled: number;
  units: number;
  revenue: number;
  aov: number | null;
  cost: number;
  profit: number | null;
  margin: number | null;
  cost_coverage: number | null;
  costed_orders: number;
  avg_days_to_ship: number | null;
  on_time_rate: number | null;
  cancel_rate: number | null;
}
interface SupplierRow extends Summary {
  supplier: string | null;
}
interface Dashboard {
  range: RangeInfo;
  kpis: Kpi[];
  totals: Summary;
  previous: Summary;
  series: { bucket: string; label: string; orders: number; revenue: number; cost: number; profit: number | null }[];
  statuses: Record<string, number>;
  top_products: { listing_id: number | null; title: string; units: number; orders: number; revenue: number; profit: number | null; margin: number | null }[];
  suppliers: SupplierRow[];
  places: { label: string; orders: number; revenue: number }[];
  options: { products: { listing_id: number; title: string }[]; suppliers: string[] };
}

const STATUS_ORDER = ["new", "purchased", "shipped", "delivered", "closed", "issue", "replacement", "return_requested", "returned", "refunded", "cancelled"];
const m = (n: number | null | undefined) => (n == null ? "—" : money(n));
const rate = (n: number | null | undefined) => (n == null ? "—" : pct(n));
const errorText = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

/** Etsy → Dashboard: how the Etsy shop is doing — sales, costs, profit, products, suppliers, shipping — for a period. */
export default function EtsyDashboard() {
  const [range, setRange] = useDateRange("30d");
  const [listing, setListing] = useState("");
  const [supplier, setSupplier] = useState("");
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setLoading(true);
    const p = new URLSearchParams({ start: range.from, end: range.to });
    if (listing) p.set("listing_id", listing);
    if (supplier) p.set("supplier", supplier);
    apiFetch<Dashboard>(`/admin/etsy/dashboard?${p}`)
      .then((d) => {
        if (!live) return;
        setData(d);
        setError(null);
      })
      .catch((e) => {
        if (live) setError(errorText(e));
      })
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, [range.from, range.to, listing, supplier]);

  const t = data?.totals;
  const series = data?.series ?? [];
  const x = series.map((s) => s.bucket);
  const xFormat = bucketFormat(data?.range.granularity);
  const money3 = [
    { key: "revenue", label: "Revenue", values: series.map((s) => s.revenue), color: "var(--color-accent)" },
    { key: "profit", label: "Net profit", values: series.map((s) => s.profit), color: "var(--viz-3)" },
    { key: "cost", label: "Costs entered", values: series.map((s) => (s.cost ? s.cost : null)), color: "var(--viz-2)" },
  ];
  const filtered = !!(listing || supplier);
  const supplierColumns: Column<SupplierRow>[] = [
    { key: "s", header: "Supplier", cell: (r) => r.supplier ?? <span className="text-muted">Not set</span> },
    { key: "o", header: "Orders", align: "right", cell: (r) => fmtInt(r.orders) },
    { key: "r", header: "Revenue", align: "right", cell: (r) => m(r.revenue) },
    { key: "c", header: "Costs", align: "right", hide: "sm", cell: (r) => m(r.cost) },
    { key: "p", header: "Profit", align: "right", cell: (r) => <span className={(r.profit ?? 0) < 0 ? "text-danger" : undefined}>{m(r.profit)}</span> },
    { key: "mg", header: "Margin", align: "right", hide: "sm", cell: (r) => rate(r.margin) },
    { key: "d", header: "Days to ship", align: "right", hide: "md", cell: (r) => (r.avg_days_to_ship == null ? "—" : r.avg_days_to_ship.toFixed(1)) },
  ];

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
      <PageHeader title="Etsy dashboard" description="How your Etsy shop is doing: sales, what it cost you, profit, best sellers, suppliers and shipping speed." />
      <ShopTabs shop="etsy" />

      <div className="flex flex-wrap items-end gap-3" role="group" aria-label="Filters">
        <DateRangePicker value={range} onChange={setRange} />
        <Field label="Product" className="w-full sm:w-72">
          {(p) => (
            <Select {...p} value={listing} onChange={(e) => setListing(e.target.value)}>
              <option value="">All products</option>
              {data?.options.products.map((o) => <option key={o.listing_id} value={o.listing_id}>{o.title}</option>)}
            </Select>
          )}
        </Field>
        <Field label="Supplier" className="w-full sm:w-56">
          {(p) => (
            <Select {...p} value={supplier} onChange={(e) => setSupplier(e.target.value)}>
              <option value="">All suppliers</option>
              <option value="__none__">Supplier not set</option>
              {data?.options.suppliers.map((s) => <option key={s} value={s}>{s}</option>)}
            </Select>
          )}
        </Field>
        {filtered ? <Button variant="ghost" size="sm" onClick={() => { setListing(""); setSupplier(""); }}>Clear filters</Button> : null}
      </div>

      {error ? <Alert tone="danger">{error}</Alert> : null}
      {t && t.orders > 0 && (t.cost_coverage ?? 1) < 1 ? (
        <Alert>
          Profit and margin count the {fmtInt(t.costed_orders)} of {fmtInt(t.orders)} orders that have a purchase cost ({rate(t.cost_coverage)}).{" "}
          <Link href="/admin/etsy/orders" className="font-medium underline">Enter the missing costs</Link> to complete them. Etsy fees are added in phase 2.
        </Alert>
      ) : null}

      <KpiStrip kpis={data?.kpis} placeholders={["Orders", "Revenue", "Net profit", "Margin", "Average order", "Days to ship"]} />

      <Panel>
        <PanelBody>
          <ChartFrame
            title="Revenue and profit"
            description={`Per ${data?.range.granularity ?? "day"}. Profit only for orders with a cost, before Etsy fees.`}
            legend={money3.map((s) => ({ label: s.label, color: s.color }))}
            table={lineTable(x, money3, (n) => money(n), xFormat)}
          >
            <LineChart x={x} series={money3} yFormat={(n) => money(n, { compact: true })} xFormat={xFormat} area={false}
              label="Revenue, net profit and costs over the period" loading={loading && !data} />
          </ChartFrame>
        </PanelBody>
      </Panel>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <Panel>
          <PanelBody>
            <ChartFrame title="Orders" description="Paid Etsy orders per period (not cancelled)."
              table={{ columns: ["Date", "Orders"], rows: series.map((s) => [xFormat(s.bucket, true), s.orders]) }}>
              <ColumnChart x={x} values={series.map((s) => s.orders)} seriesLabel="Orders" xFormat={xFormat} label="Orders per period" loading={loading && !data} />
            </ChartFrame>
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Orders by status" description="Where this period's orders are now." />
          <PanelBody>
            <BarList
              items={STATUS_ORDER.filter((s) => data?.statuses[s]).map((s, i) => ({
                label: STATUS_LABEL[s] ?? s, value: data!.statuses[s], color: s === "cancelled" ? "var(--color-muted)" : `var(--viz-${(i % 8) + 1})`,
              }))}
              format={fmtInt}
              empty="No orders in this period."
            />
          </PanelBody>
        </Panel>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Best sellers" description="By revenue. Profit of a multi-item order is shared by item price." />
          <PanelBody>
            <BarList
              items={(data?.top_products ?? []).map((p) => ({
                label: p.title,
                value: p.revenue,
                display: m(p.revenue),
                sub: `${fmtInt(p.units)} sold · ${p.profit == null ? "profit not known yet" : `${m(p.profit)} profit (${rate(p.margin)})`}`,
              }))}
              empty="Nothing sold in this period."
            />
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Where buyers are" description="US states, or country outside the US." />
          <PanelBody>
            <BarList
              items={(data?.places ?? []).map((p) => ({ label: p.label, value: p.revenue, display: m(p.revenue), sub: `${fmtInt(p.orders)} order${p.orders === 1 ? "" : "s"}` }))}
              color="var(--viz-7)"
              empty="No orders in this period."
            />
          </PanelBody>
        </Panel>
      </div>

      <Panel>
        <PanelHeader title="Suppliers" description="What each supplier's orders brought in and cost. Profit only where a cost is entered." />
        <DataTable columns={supplierColumns} rows={data ? data.suppliers : null} rowKey={(r) => r.supplier ?? "none"} caption="Suppliers" loading={loading} empty="No orders in this period." />
      </Panel>

      <Panel>
        <PanelHeader title="Shipping and cancellations" />
        <PanelBody>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              ["Average days to ship", t?.avg_days_to_ship == null ? "—" : t.avg_days_to_ship.toFixed(1)],
              ["Shipped by Etsy's date", rate(t?.on_time_rate)],
              ["Units sold", t ? fmtInt(t.units) : "—"],
              ["Cancelled", t ? `${fmtInt(t.cancelled)} (${rate(t.cancel_rate)})` : "—"],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-sm text-muted">{label}</dt>
                <dd className="num font-admin mt-1 text-2xl font-bold">{value}</dd>
              </div>
            ))}
          </dl>
        </PanelBody>
      </Panel>
    </div>
  );
}
