"use client";

import Link from "next/link";
import { Empty, Loading, ReportHeader, bucketFormat, useReport, type RangeInfo } from "@/components/admin/analytics/common";
import { BarList } from "@/components/admin/charts/BarList";
import { ChartFrame } from "@/components/admin/charts/ChartFrame";
import { Heatmap } from "@/components/admin/charts/Heatmap";
import { LineChart, lineTable } from "@/components/admin/charts/LineChart";
import { fmtInt, money, seriesColor, timeAgo } from "@/components/admin/charts/format";
import { rate } from "@/components/admin/reports";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";

interface Segment {
  key: string;
  label: string;
  help: string;
  customers: number;
  revenue: number;
  revenue_share: number | null;
}
interface TopCustomer {
  email: string;
  name: string | null;
  orders: number;
  revenue: number;
  last_order_at: string;
}
interface CustomersReport {
  range: RangeInfo;
  lifetime: {
    customers: number;
    repeat_customers: number;
    repeat_rate: number | null;
    avg_lifetime_value: number;
    avg_orders: number;
    median_days_to_second_order: number | null;
    second_orders: number;
  };
  in_range: { customers: number; new_customers: number; returning_customers: number; new_share: number | null };
  segments: Segment[];
  new_vs_returning: { bucket: string; new_orders: number; returning_orders: number }[];
  top_customers: TopCustomer[];
  geo: { region: string; country: string; customers: number; revenue: number }[];
  cohorts: { cohort: string; label: string; size: number; returned: number[]; retention: (number | null)[] }[];
  newsletter: { subscribers: number; joined: number; left: number; net: number; by_source: { source: string | null; subscribers: number }[] };
}

const MAX_MONTHS = 12;

export default function CustomersReportPage() {
  const { range, setRange, data, loading, error } = useReport<CustomersReport>("customers");
  const l = data?.lifetime;
  const r = data?.in_range;
  const mix = data?.new_vs_returning ?? [];
  const xFormat = bucketFormat(data?.range.granularity);
  const lines = [
    { key: "new", label: "First orders", values: mix.map((s) => s.new_orders), color: seriesColor(0) },
    { key: "returning", label: "Repeat orders", values: mix.map((s) => s.returning_orders), color: seriesColor(2) },
  ];
  const cohorts = (data?.cohorts ?? []).slice(-12);
  const months = Math.min(MAX_MONTHS, Math.max(0, ...cohorts.map((c) => c.retention.length - 1)));
  const topCols: Column<TopCustomer>[] = [
    {
      key: "who",
      header: "Customer",
      cell: (c) => (
        <Link href={`/admin/customers?q=${encodeURIComponent(c.email)}`} className="block min-w-0 hover:underline">
          <span className="block max-w-[16rem] truncate font-medium">{c.name || c.email}</span>
          {c.name && <span className="block max-w-[16rem] truncate text-xs text-muted">{c.email}</span>}
        </Link>
      ),
    },
    { key: "orders", header: "Orders", align: "right", cell: (c) => <span className="num">{c.orders}</span> },
    { key: "revenue", header: "Spent", align: "right", cell: (c) => <span className="num">{money(c.revenue)}</span> },
    { key: "last", header: "Last order", hide: "md", cell: (c) => <span className="text-sm text-muted">{timeAgo(c.last_order_at)}</span> },
  ];

  return (
    <div>
      <ReportHeader
        title="Customer insights"
        description="Who buys, who comes back, and who is drifting away. Lifetime figures cover every order ever; the rest follow the selected period."
        range={range}
        onRange={setRange}
        exportKind="customers"
        error={error}
      />
      <MetricStrip
        items={[
          { label: "Customers", value: l ? fmtInt(l.customers) : "—", hint: "Everyone who has ever paid for an order" },
          { label: "Repeat rate", value: l ? rate(l.repeat_rate) : "—", hint: l ? `${fmtInt(l.repeat_customers)} ordered more than once` : undefined },
          { label: "Lifetime value", value: l ? money(l.avg_lifetime_value) : "—", hint: l ? `Average spend, ${l.avg_orders} orders each` : undefined },
          {
            label: "Time to second order",
            value: l?.median_days_to_second_order != null ? `${l.median_days_to_second_order} days` : "—",
            hint: "Median; a good moment for a follow-up email",
          },
          { label: "Ordered in period", value: r ? fmtInt(r.customers) : "—", hint: r ? `${r.new_customers} new · ${r.returning_customers} returning` : undefined },
        ]}
      />

      <Panel className="mt-6">
        <PanelHeader
          title="Segments"
          description="Customers grouped by how recently, how often and how much they buy. Send each group a fitting email from Email campaigns."
          actions={
            <Link href="/admin/campaigns" className="text-sm font-medium text-accent underline underline-offset-4">
              Email a segment
            </Link>
          }
        />
        {!data ? (
          <PanelBody>
            <Loading />
          </PanelBody>
        ) : (
          <ul className="divide-y divide-line">
            {data.segments.map((s) => (
              <li key={s.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-4 gap-y-1 px-5 py-3 text-sm sm:grid-cols-[10rem_minmax(0,1fr)_6rem_8rem]">
                <Link href={`/admin/customers?segment=${s.key}`} className="font-medium hover:underline">
                  {s.label}
                </Link>
                <span className="text-muted max-sm:order-3 max-sm:col-span-2">{s.help}</span>
                <span className="num text-right">{fmtInt(s.customers)}</span>
                <span className="num text-right text-muted max-sm:hidden">
                  {money(s.revenue)} · {rate(s.revenue_share, 0)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <ChartFrame
          title="First and repeat orders"
          legend={lines.map((x) => ({ label: x.label, color: x.color }))}
          table={lineTable(mix.map((s) => s.bucket), lines, String, xFormat)}
        >
          <LineChart x={mix.map((s) => s.bucket)} series={lines} xFormat={xFormat} label="First and repeat orders over the period" loading={loading && !data} />
        </ChartFrame>
        <Panel>
          <PanelHeader title="Where customers live" description="Customers who ordered in the period." />
          <PanelBody>
            {data ? (
              <BarList
                items={data.geo.map((g) => ({ label: `${g.region}, ${g.country}`, value: g.customers, display: fmtInt(g.customers), sub: money(g.revenue) }))}
                color="var(--viz-2)"
                empty="No orders in this period yet."
              />
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
      </div>

      <Panel className="mt-6">
        <PanelHeader
          title="Do customers come back?"
          description="Each row is the month of a customer's first order; each cell is the share of them who ordered again that many months later."
        />
        <PanelBody>
          {!data ? (
            <Loading />
          ) : cohorts.length === 0 ? (
            <Empty>No orders yet.</Empty>
          ) : (
            <div className="relative">
              <Heatmap
                rowHeader="First order"
                columns={Array.from({ length: months }, (_, i) => `+${i + 1} mo`)}
                rows={cohorts.map((c) => ({ label: c.label, sub: String(c.size), cells: Array.from({ length: months }, (_, i) => c.retention[i + 1] ?? null) }))}
                caption="Share of customers ordering again, by month of first order (number after the month is customers)"
              />
              {months === 0 && <p className="mt-2 text-sm text-muted">Come back next month to see the first repeat figures.</p>}
            </div>
          )}
        </PanelBody>
      </Panel>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="Best customers" description="By lifetime spend." />
          <DataTable columns={topCols} rows={data?.top_customers ?? null} rowKey={(c) => c.email} caption="Best customers" empty="No customers yet." />
        </Panel>
        <Panel>
          <PanelHeader title="Newsletter" />
          <PanelBody className="space-y-5">
            {data ? (
              <>
                <MetricStrip
                  items={[
                    { label: "Subscribers", value: fmtInt(data.newsletter.subscribers) },
                    { label: "Change in period", value: `${data.newsletter.net >= 0 ? "+" : ""}${data.newsletter.net}`, hint: `${data.newsletter.joined} joined · ${data.newsletter.left} left` },
                  ]}
                />
                <BarList
                  items={data.newsletter.by_source.map((s) => ({ label: s.source ?? "Unknown", value: s.subscribers, display: fmtInt(s.subscribers) }))}
                  color="var(--viz-3)"
                  empty="No subscribers yet."
                />
              </>
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
