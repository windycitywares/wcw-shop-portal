"use client";

import { Empty, KpiStrip, Loading, ReportHeader, bucketFormat, useReport, type RangeInfo } from "@/components/admin/analytics/common";
import { BarList } from "@/components/admin/charts/BarList";
import { ChartFrame } from "@/components/admin/charts/ChartFrame";
import { ColumnChart } from "@/components/admin/charts/ColumnChart";
import { Heatmap } from "@/components/admin/charts/Heatmap";
import { LineChart, lineTable } from "@/components/admin/charts/LineChart";
import { money, seriesColor } from "@/components/admin/charts/format";
import { rate, type Kpi } from "@/components/admin/reports";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";

interface SalesReport {
  range: RangeInfo;
  kpis: Kpi[];
  totals: { orders: number; lines_without_cost: number; lines: number; cost_coverage: number | null };
  series: { bucket: string; label: string; orders: number; gross: number; refunds: number; net: number }[];
  by_category: { category_id: number; category: string; units: number; merchandise: number; orders: number }[];
  by_payment: { method: string; orders: number; gross: number }[];
  by_region: { label: string; orders: number; gross: number; share: number | null }[];
  heatmap: { days: { day: string; hours: number[] }[]; max: number };
  order_sizes: { band: string; orders: number; gross: number; share: number | null }[];
  discount_split: Record<"discounted" | "full_price", { orders: number; gross: number; aov: number | null }>;
  new_returning: { new_customers: number; returning_customers: number; series: { bucket: string; new_orders: number; returning_orders: number }[] };
  fulfillment: { shipped: number; hours_to_ship: number; days_in_transit: number; unshipped_over_2d: number; awaiting_payment: number; awaiting_payment_value: number };
}

const PAYMENT: Record<string, string> = { stripe: "Card (Stripe)", manual: "Manual / invoice", unknown: "Not recorded" };
const BLOCKS = ["12–3am", "3–6am", "6–9am", "9am–12", "12–3pm", "3–6pm", "6–9pm", "9pm–12"];

export default function SalesReportPage() {
  const { range, setRange, data, loading, error } = useReport<SalesReport>("sales");
  const series = data?.series ?? [];
  const x = series.map((s) => s.bucket);
  const xFormat = bucketFormat(data?.range.granularity);
  const lines = [
    { key: "net", label: "Net revenue", values: series.map((s) => s.net), color: "var(--color-accent)" },
    { key: "refunds", label: "Refunds", values: series.map((s) => s.refunds), color: "var(--color-danger)" },
  ];
  const mix = data?.new_returning.series ?? [];
  const mixLines = [
    { key: "new", label: "First orders", values: mix.map((s) => s.new_orders), color: seriesColor(0) },
    { key: "returning", label: "Repeat orders", values: mix.map((s) => s.returning_orders), color: seriesColor(2) },
  ];

  // Day × hour in 3-hour blocks, shaded against the busiest block.
  const blocks = (data?.heatmap.days ?? []).map((d) => ({ day: d.day, cells: BLOCKS.map((_, b) => d.hours.slice(b * 3, b * 3 + 3).reduce((a, n) => a + n, 0)) }));
  const busiest = Math.max(1, ...blocks.flatMap((b) => b.cells));
  const f = data?.fulfillment;
  const split = data?.discount_split;

  return (
    <div>
      <ReportHeader
        title="Sales report"
        description="Paid orders, counted on the day they were paid. Refunds are counted on the day they were made."
        range={range}
        onRange={setRange}
        exportKind="sales"
        error={error}
      />
      <KpiStrip kpis={data?.kpis} placeholders={["Net revenue", "Gross sales", "Orders", "Average order value"]} spark={{ net: series.map((s) => s.net), orders: series.map((s) => s.orders) }} />
      {data && data.totals.lines > 0 && (data.totals.cost_coverage ?? 0) < 1 && (
        <p className="mt-2 text-xs text-muted">
          Profit only counts items with a cost price ({data.totals.lines_without_cost} of {data.totals.lines} order lines have none). Add cost prices on the product page to see it in full.
        </p>
      )}

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <ChartFrame
          title="Revenue over time"
          description="Net revenue (order totals minus refunds) and refunds."
          legend={[
            { label: "Net revenue", color: "var(--color-accent)" },
            { label: "Refunds", color: "var(--color-danger)" },
          ]}
          table={lineTable(x, lines, (n) => money(n), xFormat)}
        >
          <LineChart x={x} series={lines} yFormat={(n) => money(n, { compact: true })} xFormat={xFormat} label="Net revenue and refunds over the period" loading={loading && !data} />
        </ChartFrame>
        <ChartFrame title="Orders" description="Paid orders per period." table={{ columns: ["Date", "Orders"], rows: series.map((s) => [xFormat(s.bucket, true), s.orders]) }}>
          <ColumnChart x={x} values={series.map((s) => s.orders)} seriesLabel="Orders" label="Orders per period" xFormat={xFormat} loading={loading && !data} />
        </ChartFrame>
      </div>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="By category" description="Merchandise sold (after item discounts)." />
          <PanelBody>
            {data ? (
              <BarList
                items={data.by_category.map((c) => ({ label: c.category, value: c.merchandise, display: money(c.merchandise), sub: `${c.units} sold · ${c.orders} orders` }))}
                empty="No sales in this period yet."
              />
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Where orders ship to" description="Order totals by state or region." />
          <PanelBody>
            {data ? (
              <BarList
                items={data.by_region.map((r) => ({ label: r.label, value: r.gross, display: money(r.gross), sub: `${r.orders} orders · ${rate(r.share, 0)} of sales` }))}
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
        <PanelHeader title="When people buy" description="Paid orders by weekday and time of day (shop time), darker is busier. Useful for timing emails and sales." />
        <PanelBody>
          {!data ? (
            <Loading />
          ) : data.heatmap.max === 0 ? (
            <Empty>No orders in this period yet.</Empty>
          ) : (
            <div className="relative">
              <Heatmap
                rowHeader="Day"
                columns={BLOCKS}
                rows={blocks.map((b) => ({ label: b.day, cells: b.cells.map((n) => n / busiest) }))}
                format={(v) => String(Math.round(v * busiest))}
                caption="Orders by day of week and time of day"
              />
            </div>
          )}
        </PanelBody>
      </Panel>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Order sizes" description="How many orders fall in each price band." />
          <PanelBody>
            {data ? (
              <BarList
                items={data.order_sizes.map((b) => ({ label: b.band, value: b.orders, display: `${b.orders} orders`, sub: `${money(b.gross)} · ${rate(b.share, 0)}` }))}
                empty="No orders yet."
              />
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Discounted vs full price" description="Do discounts lead to bigger or smaller orders?" />
          <PanelBody>
            {split ? (
              <MetricStrip
                items={[
                  { label: "Full-price orders", value: String(split.full_price.orders), hint: split.full_price.aov != null ? `${money(split.full_price.aov)} average` : undefined },
                  { label: "Discounted orders", value: String(split.discounted.orders), hint: split.discounted.aov != null ? `${money(split.discounted.aov)} average` : undefined },
                ]}
              />
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
      </div>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <ChartFrame
          title="First and repeat orders"
          description={data ? `${data.new_returning.new_customers} new and ${data.new_returning.returning_customers} returning customers ordered in this period.` : "New and returning customers."}
          legend={mixLines.map((l) => ({ label: l.label, color: l.color }))}
          table={lineTable(mix.map((s) => s.bucket), mixLines, String, xFormat)}
        >
          <LineChart x={mix.map((s) => s.bucket)} series={mixLines} xFormat={xFormat} label="First and repeat orders over the period" loading={loading && !data} />
        </ChartFrame>
        <Panel>
          <PanelHeader title="Shipping and payment" />
          <PanelBody className="space-y-5">
            {f ? (
              <MetricStrip
                items={[
                  { label: "Shipped", value: String(f.shipped) },
                  { label: "Paid to shipped", value: f.shipped ? `${f.hours_to_ship} h` : "—", hint: "Average" },
                  { label: "In transit", value: f.shipped ? `${f.days_in_transit} days` : "—", hint: "Average, where delivery was recorded" },
                  { label: "Waiting 2+ days", value: String(f.unshipped_over_2d), hint: "Paid but not shipped" },
                ]}
              />
            ) : (
              <Loading />
            )}
            {data && (
              <BarList
                items={data.by_payment.map((p) => ({ label: PAYMENT[p.method] ?? p.method, value: p.gross, display: money(p.gross), sub: `${p.orders} orders` }))}
                color="var(--viz-3)"
                empty="No payments yet."
              />
            )}
            {f && f.awaiting_payment > 0 && (
              <p className="text-sm text-muted">
                {f.awaiting_payment} order{f.awaiting_payment === 1 ? " is" : "s are"} waiting for payment ({money(f.awaiting_payment_value)}).
              </p>
            )}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
