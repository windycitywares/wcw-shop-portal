"use client";

import { Empty, Loading, ReportHeader, useReport, type RangeInfo } from "@/components/admin/analytics/common";
import { fmtInt } from "@/components/admin/charts/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill, type Tone } from "@/components/admin/ui/Pill";

interface Vital {
  name: string;
  samples: number;
  p75: number;
  median: number;
  rating: "good" | "needs work" | "poor" | "unknown";
  unit: string;
  good_under: number | null;
  meaning: string;
}
interface PerformanceReport {
  range: RangeInfo;
  vitals: Vital[];
  by_device: { device: string; p75: Record<string, number> }[];
  slowest_pages: { path: string; samples: number; lcp_p75: number }[];
  errors: { message: string | null; path: string | null; occurrences: number }[];
  note: string;
}

const RATING: Record<Vital["rating"], { label: string; tone: Tone }> = {
  good: { label: "Good", tone: "success" },
  "needs work": { label: "Needs work", tone: "warning" },
  poor: { label: "Poor", tone: "danger" },
  unknown: { label: "Not rated", tone: "neutral" },
};
const ORDER = ["LCP", "INP", "CLS", "FCP", "TTFB"];

function show(value: number, unit: string) {
  if (unit === "ms") return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${Math.round(value)} ms`;
  return value.toFixed(2);
}

export default function PerformanceReportPage() {
  const { range, setRange, data, error } = useReport<PerformanceReport>("performance");
  const vitals = [...(data?.vitals ?? [])].sort((a, b) => ORDER.indexOf(a.name) - ORDER.indexOf(b.name));
  const units = Object.fromEntries(vitals.map((v) => [v.name, v.unit]));
  const shown = ORDER.filter((n) => vitals.some((v) => v.name === n));

  const deviceCols: Column<PerformanceReport["by_device"][number]>[] = [
    { key: "device", header: "Device", cell: (d) => <span className="font-medium capitalize">{d.device}</span> },
    ...shown.map((n) => ({
      key: n,
      header: n,
      align: "right" as const,
      cell: (d: PerformanceReport["by_device"][number]) => <span className="num">{d.p75[n] != null ? show(d.p75[n], units[n]) : "—"}</span>,
    })),
  ];
  const pageCols: Column<PerformanceReport["slowest_pages"][number]>[] = [
    { key: "path", header: "Page", cell: (p) => <span className="block max-w-[22rem] truncate font-mono text-xs">{p.path}</span> },
    { key: "lcp", header: "Main content (p75)", align: "right", cell: (p) => <span className={p.lcp_p75 > 2500 ? "num font-medium text-danger" : "num"}>{show(p.lcp_p75, "ms")}</span> },
    { key: "samples", header: "Visits measured", align: "right", hide: "md", cell: (p) => <span className="num">{fmtInt(p.samples)}</span> },
  ];
  const errorCols: Column<PerformanceReport["errors"][number]>[] = [
    { key: "message", header: "Error", cell: (e) => <span className="block max-w-[28rem] break-words font-mono text-xs">{e.message ?? "(no message)"}</span> },
    { key: "path", header: "Page", hide: "md", cell: (e) => <span className="font-mono text-xs">{e.path ?? "—"}</span> },
    { key: "n", header: "Times", align: "right", cell: (e) => <span className="num">{fmtInt(e.occurrences)}</span> },
  ];

  return (
    <div>
      <ReportHeader
        title="Site speed"
        description="How fast the shop feels in real visitors' browsers (Google's Core Web Vitals, which also affect search ranking), and errors visitors ran into."
        range={range}
        onRange={setRange}
        error={error}
      />

      <Panel>
        <PanelHeader title="Core Web Vitals" description={data?.note ?? "75th percentile: three out of four visits were at least this fast."} />
        {!data ? (
          <PanelBody>
            <Loading />
          </PanelBody>
        ) : vitals.length === 0 ? (
          <PanelBody>
            <Empty>No measurements yet. They are collected from visitors who accept analytics.</Empty>
          </PanelBody>
        ) : (
          <ul className="grid grid-cols-[minmax(0,1fr)] divide-y divide-line sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-3">
            {vitals.map((v) => (
              <li key={v.name} className="space-y-1.5 px-5 py-4 sm:border-b sm:border-line">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{v.name}</span>
                  <Pill tone={RATING[v.rating].tone}>{RATING[v.rating].label}</Pill>
                </div>
                <p className="num text-2xl font-semibold">{show(v.p75, v.unit)}</p>
                <p className="text-xs text-muted">
                  {v.meaning}. Good is {v.good_under != null ? `under ${show(v.good_under, v.unit)}` : "—"}; {fmtInt(v.samples)} visits measured.
                </p>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel className="mt-6">
        <PanelHeader title="By device" description="Phones are usually slower; most shoppers browse on them." />
        <DataTable columns={deviceCols} rows={data?.by_device ?? null} rowKey={(d) => d.device} caption="Web vitals by device (75th percentile)" empty="No measurements yet." />
      </Panel>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-2">
        <Panel>
          <PanelHeader title="Slowest pages" description="Large photos are the usual cause. Over 2.5 s is shown in red." />
          <DataTable columns={pageCols} rows={data?.slowest_pages ?? null} rowKey={(p) => p.path} caption="Slowest pages" empty="No measurements yet." />
        </Panel>
        <Panel>
          <PanelHeader title="Errors in visitors' browsers" description="Pass these on to whoever maintains the site." />
          <DataTable columns={errorCols} rows={data?.errors ?? null} rowKey={(e) => `${e.message}|${e.path}`} caption="Browser errors" empty="No errors recorded." />
        </Panel>
      </div>
    </div>
  );
}
