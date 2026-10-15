"use client";

import Link from "next/link";
import { KpiStrip, Loading, ReportHeader, useReport, type RangeInfo } from "@/components/admin/analytics/common";
import { BarList } from "@/components/admin/charts/BarList";
import { dateTime, fmtInt, money } from "@/components/admin/charts/format";
import { rate, type Kpi } from "@/components/admin/reports";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";

interface SaleRow {
  id: number;
  name: string;
  status: "live" | "scheduled" | "ended" | "paused";
  units: number;
  orders: number;
  revenue: number;
  given_away: number;
  avg_discount: number | null;
}
interface CouponRow {
  coupon_id: number | null;
  code: string;
  source: string;
  orders: number;
  discount: number;
  revenue: number;
  return_per_dollar: number | null;
}
interface CampaignRow {
  id: number;
  name: string;
  recipients: number;
  sent_at: string;
  coupons: number;
  redeemed: number;
  redemption_rate: number | null;
  revenue: number;
}
interface PromotionsReport {
  range: RangeInfo;
  kpis: Kpi[];
  summary: { discounts: number; discounted_orders: number; avg_discount_per_order: number | null };
  sales: SaleRow[];
  coupons: CouponRow[];
  sources: { source: string; label: string; issued: number; redeemed: number; redemption_rate: number | null; discount: number; revenue: number }[];
  offers: { type: string; label: string; orders: number; discount: number }[];
  campaigns: CampaignRow[];
  carts: {
    started: number;
    abandoned: number;
    abandonment_rate: number | null;
    checkout_completion: number | null;
    recovery: { carts_reminded: number; reminders_sent: number; recovered: number; recovered_revenue: number; recovery_rate: number | null };
  };
}

const STATUS: Record<SaleRow["status"], { label: string; tone: Tone }> = {
  live: { label: "Live", tone: "success" },
  scheduled: { label: "Scheduled", tone: "info" },
  ended: { label: "Ended", tone: "neutral" },
  paused: { label: "Paused", tone: "warning" },
};

export default function PromotionsReportPage() {
  const { range, setRange, data, error } = useReport<PromotionsReport>("promotions");
  const carts = data?.carts;

  const saleCols: Column<SaleRow>[] = [
    {
      key: "name",
      header: "Sale",
      cell: (s) => (
        <span className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{s.name}</span>
          <Pill tone={STATUS[s.status].tone}>{STATUS[s.status].label}</Pill>
        </span>
      ),
    },
    { key: "units", header: "Sold", align: "right", hide: "md", cell: (s) => <span className="num">{fmtInt(s.units)}</span> },
    { key: "revenue", header: "Revenue", align: "right", cell: (s) => <span className="num">{money(s.revenue)}</span> },
    { key: "given", header: "Given away", align: "right", cell: (s) => <span className="num">{money(s.given_away)}</span> },
    { key: "avg", header: "Avg. off", align: "right", hide: "lg", cell: (s) => <span className="num">{rate(s.avg_discount, 0)}</span> },
  ];
  const couponCols: Column<CouponRow>[] = [
    { key: "code", header: "Code", cell: (c) => <span className="num font-medium">{c.code}</span> },
    { key: "orders", header: "Orders", align: "right", cell: (c) => <span className="num">{fmtInt(c.orders)}</span> },
    { key: "discount", header: "Discount", align: "right", cell: (c) => <span className="num">{money(c.discount)}</span> },
    { key: "revenue", header: "Revenue", align: "right", hide: "md", cell: (c) => <span className="num">{money(c.revenue)}</span> },
    {
      key: "return",
      header: "Per $1 off",
      align: "right",
      hide: "md",
      cell: (c) => (
        <span className="num" title="Revenue brought in for every dollar of discount">
          {c.return_per_dollar != null ? money(c.return_per_dollar) : "—"}
        </span>
      ),
    },
  ];
  const campaignCols: Column<CampaignRow>[] = [
    {
      key: "name",
      header: "Campaign",
      cell: (c) => (
        <span className="block min-w-0">
          <span className="block max-w-[18rem] truncate font-medium">{c.name}</span>
          <span className="text-xs text-muted">
            {dateTime(c.sent_at)} · {fmtInt(c.recipients)} sent
          </span>
        </span>
      ),
    },
    { key: "redeemed", header: "Used a code", align: "right", cell: (c) => <span className="num">{`${c.redeemed} (${rate(c.redemption_rate, 0)})`}</span> },
    { key: "revenue", header: "Revenue", align: "right", cell: (c) => <span className="num">{money(c.revenue)}</span> },
  ];

  return (
    <div>
      <ReportHeader
        title="Promotion results"
        description="What sales, coupons, automatic offers and emails cost, and what they brought back. A good promotion brings in several dollars for every dollar off."
        range={range}
        onRange={setRange}
        exportKind="promotions"
        error={error}
      />
      <KpiStrip kpis={data?.kpis} placeholders={["Discounts given", "Discount rate", "Orders with a discount", "Sale price savings"]} />

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-2">
        <Panel>
          <PanelHeader
            title="Sales"
            actions={
              <Link href="/admin/promotions?tab=sales" className="text-sm font-medium text-accent underline underline-offset-4">
                Manage sales
              </Link>
            }
          />
          <DataTable columns={saleCols} rows={data?.sales ?? null} rowKey={(s) => s.id} caption="Sale results" empty="No sales ran in this period." />
        </Panel>
        <Panel>
          <PanelHeader
            title="Coupons used"
            actions={
              <Link href="/admin/promotions?tab=coupons" className="text-sm font-medium text-accent underline underline-offset-4">
                Manage coupons
              </Link>
            }
          />
          <DataTable columns={couponCols} rows={data?.coupons ?? null} rowKey={(c) => c.coupon_id ?? c.code} caption="Coupon results" empty="No coupons used in this period." />
        </Panel>
      </div>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Where coupons come from" description="Codes issued in the period and how many were used." />
          <PanelBody>
            {data ? (
              <BarList
                items={data.sources.map((s) => ({
                  label: s.label,
                  value: s.redeemed,
                  display: `${s.redeemed} of ${s.issued} used`,
                  sub: `${rate(s.redemption_rate, 0)} · ${money(s.discount)} off · ${money(s.revenue)} revenue`,
                }))}
                empty="No coupons issued in this period."
              />
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Automatic offers" description="Cart offers such as spend-and-save or free shipping." />
          <PanelBody>
            {data ? (
              <BarList
                items={data.offers.map((o) => ({ label: o.label || o.type, value: o.discount, display: money(o.discount), sub: `${o.orders} orders` }))}
                color="var(--viz-2)"
                empty="No automatic offers were applied in this period."
              />
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
      </div>

      <Panel className="mt-6">
        <PanelHeader title="Email campaigns" description="Campaigns sent in the period and the coupon orders they led to." />
        <DataTable columns={campaignCols} rows={data?.campaigns ?? null} rowKey={(c) => c.id} caption="Campaign results" empty="No campaigns sent in this period." />
      </Panel>

      <Panel className="mt-6">
        <PanelHeader
          title="Carts and reminders"
          actions={
            <Link href="/admin/carts" className="text-sm font-medium text-accent underline underline-offset-4">
              See carts
            </Link>
          }
        />
        <PanelBody>
          {carts ? (
            <MetricStrip
              items={[
                { label: "Carts started", value: fmtInt(carts.started) },
                { label: "Abandoned", value: rate(carts.abandonment_rate, 0), hint: `${fmtInt(carts.abandoned)} carts` },
                { label: "Checkout completed", value: rate(carts.checkout_completion, 0), hint: "Of carts that reached checkout" },
                { label: "Reminders sent", value: fmtInt(carts.recovery.reminders_sent), hint: `${fmtInt(carts.recovery.carts_reminded)} carts` },
                {
                  label: "Recovered",
                  value: fmtInt(carts.recovery.recovered),
                  hint: `${money(carts.recovery.recovered_revenue)} · ${rate(carts.recovery.recovery_rate, 0)} of reminded carts`,
                },
              ]}
            />
          ) : (
            <Loading />
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
