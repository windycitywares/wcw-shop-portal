"use client";

import { useState } from "react";
import { Empty, Loading, ReportHeader, useReport, type RangeInfo } from "@/components/admin/analytics/common";
import { Funnel } from "@/components/admin/charts/Funnel";
import { Heatmap } from "@/components/admin/charts/Heatmap";
import { fmtInt, pct } from "@/components/admin/charts/format";
import { CHANNEL_LABEL, rate } from "@/components/admin/reports";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Tabs } from "@/components/admin/ui/Tabs";

interface Step {
  key: string;
  label: string;
  count: number;
  of_previous: number | null;
  of_total: number | null;
  lost: number;
}
interface Group {
  label: string;
  sessions: number;
  viewed_rate: number | null;
  cart_rate: number | null;
  checkout_rate: number | null;
  order_rate: number | null;
  paid_rate: number | null;
}
interface FunnelReport {
  range: RangeInfo;
  steps: Step[];
  overall_conversion: number | null;
  biggest_drop: { from: string; to: string; lost: number; kept: number | null } | null;
  by_device: Group[];
  by_channel: Group[];
  note: string;
}

const HINTS: Record<string, string> = {
  viewed: "Opened at least one product page",
  carted: "Put something in the cart",
  checkout: "Opened checkout",
  ordered: "Submitted an order",
  paid: "Payment received",
};
const RATE_COLUMNS = ["Viewed", "Cart", "Checkout", "Ordered", "Paid"];
type By = "by_device" | "by_channel";

export default function FunnelReportPage() {
  const { range, setRange, data, error } = useReport<FunnelReport>("funnel");
  const [by, setBy] = useState<By>("by_device");
  const groups = data?.[by] ?? [];
  const drop = data?.biggest_drop;

  return (
    <div>
      <ReportHeader
        title="Shopping funnel"
        description="How many visits reach each step, from first page to paid order. Only visitors who accepted analytics are counted."
        range={range}
        onRange={setRange}
        exportKind="funnel"
        error={error}
      />
      <MetricStrip
        items={[
          { label: "Visits", value: data ? fmtInt(data.steps[0]?.count ?? 0) : "—" },
          { label: "Visit to paid order", value: data ? rate(data.overall_conversion, 2) : "—", hint: "Small shops usually sit between 1% and 3%" },
          {
            label: "Biggest drop",
            value: drop ? `${drop.from} → ${drop.to}` : "—",
            hint: drop ? `${fmtInt(drop.lost)} visits stopped here${drop.kept != null ? ` (${pct(drop.kept, 0)} continued)` : ""}` : "Needs at least 20 visits at a step",
          },
        ]}
      />

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="Steps" description="The percentage is the share that continued from the step before." />
          <PanelBody>
            {!data ? (
              <Loading />
            ) : (data.steps[0]?.count ?? 0) === 0 ? (
              <Empty>No tracked visits in this period yet.</Empty>
            ) : (
              <Funnel stages={data.steps.map((s) => ({ label: s.label, value: s.count, hint: HINTS[s.key] }))} />
            )}
            {data && <p className="mt-4 text-xs text-muted">{data.note}</p>}
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Compare groups" description="Share of each group's visits that reached the step. Look for a group far below the others." />
          <div className="px-4 pt-1">
            <Tabs<By>
              tabs={[
                { id: "by_device", label: "Device" },
                { id: "by_channel", label: "Source" },
              ]}
              value={by}
              onChange={setBy}
              label="Compare by"
            />
          </div>
          <PanelBody>
            {!data ? (
              <Loading />
            ) : groups.length === 0 ? (
              <Empty>No tracked visits yet.</Empty>
            ) : (
              <div className="relative">
                <Heatmap
                  rowHeader={by === "by_device" ? "Device" : "Source"}
                  columns={RATE_COLUMNS}
                  rows={groups.map((g) => ({
                    label: by === "by_channel" ? (CHANNEL_LABEL[g.label] ?? g.label) : g.label.charAt(0).toUpperCase() + g.label.slice(1),
                    sub: `${fmtInt(g.sessions)}`,
                    cells: [g.viewed_rate, g.cart_rate, g.checkout_rate, g.order_rate, g.paid_rate],
                  }))}
                  format={(v) => pct(v, v < 0.1 ? 1 : 0)}
                  caption="Share of visits reaching each step, by group (number after the name is visits)"
                />
              </div>
            )}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
