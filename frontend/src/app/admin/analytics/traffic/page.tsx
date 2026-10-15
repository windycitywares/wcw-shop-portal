"use client";

import { useState } from "react";
import { Empty, KpiStrip, Loading, ReportHeader, bucketFormat, useReport, type RangeInfo } from "@/components/admin/analytics/common";
import { BarList } from "@/components/admin/charts/BarList";
import { ChartFrame } from "@/components/admin/charts/ChartFrame";
import { LineChart, lineTable } from "@/components/admin/charts/LineChart";
import { fmtInt, money, seriesColor } from "@/components/admin/charts/format";
import { CHANNEL_LABEL, rate, type Kpi } from "@/components/admin/reports";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Tabs } from "@/components/admin/ui/Tabs";

interface Share {
  label: string | null;
  sessions: number;
  share: number | null;
  bounce_rate: number | null;
}
interface Channel {
  channel: string;
  sessions: number;
  visitors: number;
  share: number | null;
  bounce_rate: number | null;
  orders: number;
  revenue: number;
  conversion: number | null;
  revenue_per_visit: number | null;
}
interface TrafficReport {
  range: RangeInfo;
  kpis: Kpi[];
  series: { bucket: string; sessions: number; visitors: number }[];
  channels: Channel[];
  devices: Share[];
  browsers: Share[];
  systems: Share[];
  languages: Share[];
  landing_pages: { path: string; sessions: number; bounce_rate: number | null; conversion: number | null }[];
  referrers: { host: string | null; channel: string; sessions: number }[];
  campaigns: { campaign: string; source: string; medium: string; sessions: number; orders: number; revenue: number; conversion: number | null }[];
  consent: { accepted: number; declined: number; rate: number | null };
  live_visitors: number;
}

type Dim = "devices" | "browsers" | "systems" | "languages";
const DIMS: { id: Dim; label: string }[] = [
  { id: "devices", label: "Device" },
  { id: "browsers", label: "Browser" },
  { id: "systems", label: "System" },
  { id: "languages", label: "Language" },
];
const LANG: Record<string, string> = { en: "English", es: "Spanish", nl: "Dutch" };

export default function TrafficReportPage() {
  const { range, setRange, data, loading, error } = useReport<TrafficReport>("traffic");
  const [dim, setDim] = useState<Dim>("devices");
  const series = data?.series ?? [];
  const x = series.map((s) => s.bucket);
  const xFormat = bucketFormat(data?.range.granularity);
  const lines = [
    { key: "sessions", label: "Visits", values: series.map((s) => s.sessions), color: seriesColor(0) },
    { key: "visitors", label: "Visitors", values: series.map((s) => s.visitors), color: seriesColor(2) },
  ];

  const channelCols: Column<Channel>[] = [
    { key: "channel", header: "Source", cell: (c) => <span className="font-medium">{CHANNEL_LABEL[c.channel] ?? c.channel}</span> },
    { key: "sessions", header: "Visits", align: "right", cell: (c) => <span className="num">{fmtInt(c.sessions)}</span> },
    { key: "share", header: "Share", align: "right", hide: "md", cell: (c) => <span className="num">{rate(c.share, 0)}</span> },
    { key: "bounce", header: "Bounce", align: "right", hide: "lg", cell: (c) => <span className="num">{rate(c.bounce_rate, 0)}</span> },
    { key: "orders", header: "Orders", align: "right", cell: (c) => <span className="num">{fmtInt(c.orders)}</span> },
    { key: "revenue", header: "Revenue", align: "right", hide: "md", cell: (c) => <span className="num">{money(c.revenue)}</span> },
    { key: "conversion", header: "Conversion", align: "right", hide: "lg", cell: (c) => <span className="num">{rate(c.conversion)}</span> },
  ];
  const landingCols: Column<TrafficReport["landing_pages"][number]>[] = [
    { key: "path", header: "First page", cell: (l) => <span className="block max-w-[20rem] truncate font-mono text-xs">{l.path}</span> },
    { key: "sessions", header: "Visits", align: "right", cell: (l) => <span className="num">{fmtInt(l.sessions)}</span> },
    { key: "bounce", header: "Bounce", align: "right", cell: (l) => <span className="num">{rate(l.bounce_rate, 0)}</span> },
    { key: "conversion", header: "Conversion", align: "right", hide: "md", cell: (l) => <span className="num">{rate(l.conversion)}</span> },
  ];

  const dimRows = data?.[dim] ?? [];

  return (
    <div>
      <ReportHeader
        title="Traffic"
        description={
          data
            ? `Where visitors come from and how they find the shop. Only visitors who accepted analytics are counted (${rate(data.consent.rate, 0)} of those who chose). ${data.live_visitors} on the site now.`
            : "Where visitors come from and how they find the shop. Only visitors who accepted analytics are counted."
        }
        range={range}
        onRange={setRange}
        exportKind="traffic"
        error={error}
      />
      <KpiStrip kpis={data?.kpis} placeholders={["Visits", "Visitors", "Bounce rate", "Conversion rate"]} spark={{ sessions: series.map((s) => s.sessions), visitors: series.map((s) => s.visitors) }} />

      <ChartFrame
        className="mt-6"
        title="Visits over time"
        description="A visit ends after 30 minutes without activity."
        legend={lines.map((l) => ({ label: l.label, color: l.color }))}
        table={lineTable(x, lines, (n) => fmtInt(n), xFormat)}
      >
        <LineChart x={x} series={lines} xFormat={xFormat} label="Visits and visitors over the period" loading={loading && !data} />
      </ChartFrame>

      <Panel className="mt-6">
        <PanelHeader title="Sources" description="Which channels bring visitors, and which of them buy. Revenue is from orders placed during a tracked visit." />
        <DataTable columns={channelCols} rows={data?.channels ?? null} rowKey={(c) => c.channel} caption="Traffic sources" empty="No tracked visits in this period yet." />
      </Panel>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Visitors' technology" />
          <div className="px-4 pt-1">
            <Tabs<Dim> tabs={DIMS} value={dim} onChange={setDim} label="Group visits by" />
          </div>
          <PanelBody>
            {data ? (
              <BarList
                items={dimRows.map((d) => {
                  const name = d.label ?? "Unknown";
                  return {
                    label: dim === "languages" ? (LANG[name] ?? name) : name.charAt(0).toUpperCase() + name.slice(1),
                    value: d.sessions,
                    display: rate(d.share, 0),
                    sub: `${fmtInt(d.sessions)} visits · ${rate(d.bounce_rate, 0)} bounce`,
                  };
                })}
                color="var(--viz-2)"
                empty="No tracked visits yet."
              />
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Referring websites" description="Other sites that sent visitors." />
          <PanelBody>
            {data ? (
              <BarList
                items={data.referrers.map((r) => ({ label: r.host ?? "Unknown", value: r.sessions, display: `${fmtInt(r.sessions)} visits`, sub: CHANNEL_LABEL[r.channel] ?? r.channel }))}
                color="var(--viz-3)"
                empty="No visits from other websites yet."
              />
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
      </div>

      <Panel className="mt-6">
        <PanelHeader title="Landing pages" description="The first page of each visit. A high bounce rate on a busy page is the best place to improve." />
        <DataTable columns={landingCols} rows={data?.landing_pages ?? null} rowKey={(l) => l.path} caption="Landing pages" empty="No tracked visits yet." />
      </Panel>

      <Panel className="mt-6">
        <PanelHeader title="Campaigns" description="Visits from links tagged with utm_campaign (newsletters, ads, social posts)." />
        <PanelBody>
          {!data ? (
            <Loading />
          ) : data.campaigns.length === 0 ? (
            <Empty>No tagged campaign visits. Add ?utm_source=…&utm_campaign=… to links you share to see them here.</Empty>
          ) : (
            <BarList
              items={data.campaigns.map((c) => ({
                label: c.campaign,
                value: c.sessions,
                display: `${fmtInt(c.sessions)} visits`,
                sub: `${[c.source, c.medium].filter(Boolean).join(" / ") || "no source"} · ${c.orders} orders · ${money(c.revenue)}`,
              }))}
            />
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
