"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import { cn } from "@/lib/utils";
import { dayLabel } from "../charts/format";
import { downloadFile } from "../download";
import { SEVERITY, formatKpi, type Insight, type Kpi } from "../reports";
import { DateRangePicker } from "../ui/DateRangePicker";
import { rangeParams, type DateRange } from "../ui/dateRange";
import { Icon } from "../ui/Icon";
import { MetricStrip } from "../ui/Metric";
import { PageHeader } from "../ui/PageHeader";
import { Pill } from "../ui/Pill";
import { useToast } from "../ui/Toast";
import { useDateRange } from "../ui/useDateRange";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/misc";

export interface RangeInfo {
  start: string;
  end: string;
  days: number;
  granularity: "day" | "week" | "month";
  previous_start: string;
  previous_end: string;
}

/** Every report, in sidebar order. `permission` is on top of reports:view. */
export const REPORTS: { slug: string; label: string; permission?: string }[] = [
  { slug: "", label: "Suggestions" },
  { slug: "sales", label: "Sales" },
  { slug: "products", label: "Products" },
  { slug: "traffic", label: "Traffic" },
  { slug: "funnel", label: "Funnel" },
  { slug: "behavior", label: "Behavior" },
  { slug: "performance", label: "Site speed" },
  { slug: "customers", label: "Customers", permission: "customers:view" },
  { slug: "promotions", label: "Promotions" },
  { slug: "inventory", label: "Inventory" },
  { slug: "catalog", label: "Catalog health" },
];

/** Links between the reports (a nav, not tabs: each report is its own page with its own address). */
export function ReportNav() {
  const pathname = usePathname();
  const { can } = useAuth();
  return (
    <nav aria-label="Reports" className="relative mb-6">
      <ul className="flex gap-1 overflow-x-auto border-b border-line">
        {REPORTS.filter((r) => !r.permission || can(r.permission)).map((r) => {
          const href = r.slug ? `/admin/analytics/${r.slug}` : "/admin/analytics";
          const current = pathname === href;
          return (
            <li key={r.slug} className="shrink-0">
              <Link
                href={href}
                aria-current={current ? "page" : undefined}
                className={cn(
                  "-mb-px block whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                  current ? "border-accent text-ink" : "border-transparent text-muted hover:text-ink",
                )}
              >
                {r.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Load `/admin/reports/<name>` for the selected range; reloads when the range changes. */
export function useReport<T>(name: string, withRange = true) {
  const [range, setRange] = useDateRange("30d");
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setLoading(true);
    apiFetch<T>(`/admin/reports/${name}${withRange ? `?${rangeParams(range)}` : ""}`)
      .then(
        (d) => {
          if (!live) return;
          setData(d);
          setError("");
        },
        (e) => live && setError(e.message),
      )
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [name, range, withRange]);
  return { range, setRange, data, loading, error };
}

/** "Download CSV" for one of the API's exports. */
export function ExportButton({ kind, range }: { kind: string; range?: DateRange }) {
  const { push } = useToast();
  const [busy, setBusy] = useState(false);
  return (
    <Button
      size="sm"
      variant="secondary"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          const name = range ? `wcw-${kind}-${range.from}-to-${range.to}.csv` : `wcw-${kind}.csv`;
          await downloadFile(`/admin/reports/export/${kind}.csv${range ? `?${rangeParams(range)}` : ""}`, name);
          push({ title: "Downloaded", description: name });
        } catch (e) {
          push({ title: "Download failed", description: e instanceof Error ? e.message : undefined, tone: "danger" });
        } finally {
          setBusy(false);
        }
      }}
    >
      <Icon name="download" className="size-4" />
      Download CSV
    </Button>
  );
}

/** Title, explanation, range picker and export for a report page, plus the error banner. */
export function ReportHeader({
  title,
  description,
  range,
  onRange,
  exportKind,
  error,
}: {
  title: string;
  description: React.ReactNode;
  range?: DateRange;
  onRange?: (r: DateRange) => void;
  exportKind?: string;
  error?: string;
}) {
  return (
    <>
      <PageHeader
        title={title}
        description={description}
        actions={
          <>
            {range && onRange && <DateRangePicker value={range} onChange={onRange} />}
            {exportKind && <ExportButton kind={exportKind} range={range} />}
          </>
        }
      />
      <ReportNav />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}
    </>
  );
}

/** The report's KPI cards as one strip, with placeholders while loading. */
export function KpiStrip({ kpis, placeholders, spark, className }: { kpis?: Kpi[]; placeholders: string[]; spark?: Record<string, number[]>; className?: string }) {
  return (
    <MetricStrip
      className={className}
      compareLabel="vs previous period"
      items={
        kpis
          ? kpis.map((k) => ({
              label: k.label,
              value: formatKpi(k),
              change: k.better === "none" ? null : k.change,
              good: k.better === "down" ? ("down" as const) : ("up" as const),
              hint: k.help || undefined,
              spark: spark?.[k.key],
            }))
          : placeholders.map((label) => ({ label, value: "—" }))
      }
    />
  );
}

/** Recommendations with their severity and a link to where to act. */
export function InsightList({ items, empty }: { items: Insight[]; empty: string }) {
  if (items.length === 0) return <p className="px-5 py-8 text-center text-sm text-muted">{empty}</p>;
  return (
    <ul className="divide-y divide-line">
      {items.map((s) => (
        <li key={s.key} className="flex flex-wrap items-start gap-x-4 gap-y-2 px-5 py-4">
          <Pill tone={SEVERITY[s.severity].tone}>{SEVERITY[s.severity].label}</Pill>
          <div className="min-w-0 flex-1 basis-64">
            <p className="text-sm font-medium">{s.title}</p>
            <p className="mt-0.5 text-sm text-muted">{s.detail}</p>
          </div>
          {s.action && s.href && (
            <Link href={s.href} className="shrink-0 text-sm font-medium text-accent underline underline-offset-4">
              {s.action}
            </Link>
          )}
        </li>
      ))}
    </ul>
  );
}

/** x-axis labels that follow the report's bucket size (days, weeks or months). */
export function bucketFormat(granularity: RangeInfo["granularity"] | undefined) {
  return (x: string, long?: boolean) =>
    granularity === "month"
      ? new Date(`${x}T12:00:00`).toLocaleDateString("en-US", { month: long ? "long" : "short", year: "numeric" })
      : granularity === "week"
        ? `${long ? "Week of " : ""}${dayLabel(x, "short")}`
        : dayLabel(x, long ? "long" : "short");
}

/** Muted line for "nothing yet" inside a panel. */
export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>;
}

/** Skeleton while a panel's data loads. */
export function Loading({ className }: { className?: string }) {
  return <div className={cn("skeleton h-32", className)} />;
}
