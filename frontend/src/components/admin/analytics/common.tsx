"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
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

/** The reports, grouped by the question each answers. `permission` is on top of reports:view. */
export interface ReportDef {
  slug: string;
  label: string;
  /** What the report needs before it has anything to show (order-based reports start empty on a new shop). */
  needs?: string;
  permission?: string;
}
export interface ReportGroup {
  id: string;
  label: string;
  question: string;
  reports: ReportDef[];
}
export const REPORT_GROUPS: ReportGroup[] = [
  { id: "overview", label: "Overview", question: "What needs my attention?", reports: [{ slug: "", label: "Suggestions" }] },
  {
    id: "visitors",
    label: "Visitors",
    question: "Who comes, from where, and is the site fast?",
    reports: [
      { slug: "traffic", label: "Traffic" },
      { slug: "behavior", label: "Behavior" },
      { slug: "performance", label: "Site speed" },
    ],
  },
  {
    id: "sales",
    label: "Sales",
    question: "What sold, and where do buyers drop off?",
    reports: [
      { slug: "sales", label: "Sales", needs: "paid orders" },
      { slug: "funnel", label: "Funnel", needs: "visits and orders" },
      { slug: "promotions", label: "Promotions", needs: "orders that used a discount" },
    ],
  },
  {
    id: "products",
    label: "Products",
    question: "What is selling, running out or needs fixing?",
    reports: [
      { slug: "products", label: "Products" },
      { slug: "inventory", label: "Inventory" },
      { slug: "catalog", label: "Catalog health" },
    ],
  },
  {
    id: "customers",
    label: "Customers",
    question: "Who buys again?",
    reports: [{ slug: "customers", label: "Customers", needs: "paid orders", permission: "customers:view" }],
  },
];
export const REPORTS: ReportDef[] = REPORT_GROUPS.flatMap((g) => g.reports);

export function groupFor(pathname: string): ReportGroup {
  const slug = pathname.replace(/^\/admin\/analytics\/?/, "").split("/")[0];
  return REPORT_GROUPS.find((g) => g.reports.some((r) => r.slug === slug)) ?? REPORT_GROUPS[0];
}

/** One date range for every report: change it once and it follows you from report to report. */
export const RangeContext = createContext<[DateRange, (r: DateRange) => void] | null>(null);

/** Sits above every report (from the analytics layout): this group's reports as links, and the one date picker. */
export function ReportBar() {
  const pathname = usePathname();
  const { can } = useAuth();
  const ctx = useContext(RangeContext);
  const group = groupFor(pathname);
  const reports = group.reports.filter((r) => !r.permission || can(r.permission));
  const current = REPORTS.find((r) => (r.slug ? pathname === `/admin/analytics/${r.slug}` : pathname === "/admin/analytics"));
  return (
    <div className="mb-6 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">{group.label}</p>
          <p className="text-sm text-muted">{group.question}</p>
        </div>
        {ctx && <DateRangePicker value={ctx[0]} onChange={ctx[1]} />}
      </div>
      {reports.length > 1 && (
        <nav aria-label={`${group.label} reports`} className="relative">
          <ul className="flex gap-1 overflow-x-auto border-b border-line">
            {reports.map((r) => {
              const href = r.slug ? `/admin/analytics/${r.slug}` : "/admin/analytics";
              const here = pathname === href;
              return (
                <li key={r.slug} className="shrink-0">
                  <Link
                    href={href}
                    aria-current={here ? "page" : undefined}
                    className={cn(
                      "-mb-px block whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                      here ? "border-accent text-ink" : "border-transparent text-muted hover:text-ink",
                    )}
                  >
                    {r.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      )}
      {current?.needs && <p className="text-xs text-muted">This report fills in as {current.needs} arrive.</p>}
    </div>
  );
}

/** Load `/admin/reports/<name>` for the selected range; reloads when the range changes. */
export function useReport<T>(name: string, withRange = true) {
  const shared = useContext(RangeContext);
  const own = useDateRange("30d");
  const [range, setRange] = shared ?? own;
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
            {exportKind && <ExportButton kind={exportKind} range={range} />}
          </>
        }
      />
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
