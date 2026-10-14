"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import type { Page, Product } from "@/lib/types";
import { BarList } from "@/components/admin/charts/BarList";
import { ChartFrame } from "@/components/admin/charts/ChartFrame";
import { LineChart, lineTable } from "@/components/admin/charts/LineChart";
import { dayLabel, money, timeAgo } from "@/components/admin/charts/format";
import { CHANNEL_LABEL, ORDER_STATUS, SEVERITY, formatKpi, type Overview } from "@/components/admin/reports";
import { DateRangePicker } from "@/components/admin/ui/DateRangePicker";
import { rangeParams } from "@/components/admin/ui/dateRange";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { StatusBar } from "@/components/admin/ui/StatusBar";
import { useDateRange } from "@/components/admin/ui/useDateRange";
import { ButtonLink } from "@/components/ui/Button";
import { Alert } from "@/components/ui/misc";

type Stats = Record<"draft" | "in_review" | "published" | "archived" | "low_stock", number>;

function greeting(now = new Date()) {
  const h = now.getHours();
  return h < 5 ? "Working late" : h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

interface Task {
  key: string;
  count: number;
  label: string;
  hint?: string;
  href?: string;
  tone: "warning" | "danger" | "info";
}

const ATTENTION_TONE = { critical: "danger", warning: "warning", info: "info" } as const;

export default function AdminDashboard() {
  const { user, can } = useAuth();
  const reports = can("reports:view");
  const [range, setRange] = useDateRange("30d");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Stats>("/products/stats").then(setStats, (e) => setError(e.message));
    apiFetch<Page<Product>>("/products?page_size=100&sort=updated&status=published&status=draft&status=in_review").then(
      (r) => setProducts(r.items),
      () => setProducts([]),
    );
  }, []);

  useEffect(() => {
    if (!reports) return;
    setLoadingOverview(true);
    apiFetch<Overview>(`/admin/reports/overview?${rangeParams(range)}`)
      .then(setOverview, (e) => setError(e.message))
      .finally(() => setLoadingOverview(false));
  }, [reports, range]);

  const health = useMemo(() => {
    const live = (products ?? []).filter((p) => p.status === "published");
    return {
      noPhoto: live.filter((p) => p.images.length === 0),
      noText: live.filter((p) => !p.description || p.description.length < 80),
      low: live
        .filter((p) => p.stock_quantity != null && p.stock_quantity > 0 && p.stock_quantity <= 3)
        .sort((a, b) => (a.stock_quantity ?? 0) - (b.stock_quantity ?? 0)),
    };
  }, [products]);

  // What needs a person today: orders and reviews from the reports, catalog fixes from the product list.
  const tasks: Task[] = [
    ...(overview?.attention ?? []).map((a) => ({ key: a.key, count: a.count, label: a.label, href: a.href, tone: ATTENTION_TONE[a.tone] })),
    ...(stats
      ? [
          { key: "review", count: stats.in_review, label: "Products waiting for review", hint: "Authors have submitted them for publishing.", href: "/admin/products?status=in_review", tone: "info" as const },
          { key: "photo", count: health.noPhoto.length, label: "Live products without a photo", hint: "Products with photos get far more clicks.", tone: "warning" as const },
          { key: "text", count: health.noText.length, label: "Live products with a very short description", hint: "A fuller description helps shoppers and search engines.", tone: "warning" as const },
        ]
      : []),
  ].filter((t) => t.count > 0);

  const series = overview?.series ?? [];
  const lines = [
    { key: "net", label: "Net revenue", values: series.map((s) => s.net) },
  ];
  const xFormat = (x: string, long?: boolean) =>
    overview?.range.granularity === "month" ? new Date(`${x}T12:00:00`).toLocaleDateString("en-US", { month: long ? "long" : "short", year: "numeric" }) : dayLabel(x, long ? "long" : "short");

  return (
    <div>
      <PageHeader
        title={`${greeting()}${user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}`}
        description={
          reports && overview
            ? `${overview.live_visitors === 1 ? "1 person is" : `${overview.live_visitors} people are`} on the shop right now (visitors who accepted analytics).`
            : "Here is the state of the shop."
        }
        actions={
          <>
            {reports && <DateRangePicker value={range} onChange={setRange} />}
            {can("catalog:create") && (
              <ButtonLink href="/admin/products/new" size="sm">
                Add product
              </ButtonLink>
            )}
          </>
        }
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}

      {reports && (
        <>
          <MetricStrip
            compareLabel="vs previous period"
            items={
              overview
                ? overview.kpis.map((k) => ({
                    label: k.label,
                    value: formatKpi(k),
                    change: k.better === "none" ? null : k.change,
                    good: k.better === "down" ? ("down" as const) : ("up" as const),
                    spark: k.key === "net" ? series.map((s) => s.net) : k.key === "orders" ? series.map((s) => s.orders) : k.key === "visitors" ? series.map((s) => s.visitors) : undefined,
                  }))
                : ["Net revenue", "Orders", "Average order", "Conversion rate", "Visitors", "New customers", "Items sold", "Refund rate"].map((label) => ({ label, value: "—" }))
            }
          />

          <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <ChartFrame
              title="Sales"
              description="Order totals minus refunds, by the day the order was paid."
              table={lineTable(series.map((s) => s.bucket), lines, (n) => money(n), xFormat)}
            >
              <LineChart x={series.map((s) => s.bucket)} series={lines} yFormat={(n) => money(n, { compact: true })} xFormat={xFormat} label="Net revenue over the selected period" loading={loadingOverview && !overview} />
            </ChartFrame>

            <Panel>
              <PanelHeader title="Needs your attention" description="Things to do today, most urgent first." />
              {(reports && !overview) || stats === null ? (
                <PanelBody>
                  <div className="skeleton h-24" />
                </PanelBody>
              ) : tasks.length === 0 ? (
                <PanelBody>
                  <p className="text-sm text-muted">Nothing needs attention right now.</p>
                </PanelBody>
              ) : (
                <ul className="divide-y divide-line">
                  {tasks.map((t) => (
                    <li key={t.key} className="flex items-center gap-4 px-5 py-3.5">
                      <Pill tone={t.tone} dot={false} className="num min-w-9 justify-center text-sm">
                        {t.count}
                      </Pill>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium">{t.label}</p>
                        {t.hint && <p className="text-sm text-muted">{t.hint}</p>}
                      </div>
                      {t.href && (
                        <Link href={t.href} className="shrink-0 text-sm font-medium text-accent underline underline-offset-4">
                          Open
                          <span className="sr-only"> {t.label}</span>
                        </Link>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <Panel className="mt-6">
            <PanelHeader
              title="Suggestions"
              description={overview ? `What would most improve sales, from this period's numbers (${overview.suggestion_count} in total).` : "From this period's numbers."}
            />
            {!overview ? (
              <PanelBody>
                <div className="skeleton h-24" />
              </PanelBody>
            ) : overview.suggestions.length === 0 ? (
              <PanelBody>
                <p className="text-sm text-muted">No suggestions for this period. Check back once there are more visits and orders.</p>
              </PanelBody>
            ) : (
              <ul className="divide-y divide-line">
                {overview.suggestions.map((s) => (
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
            )}
          </Panel>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Panel>
              <PanelHeader title="Best sellers" description="Merchandise sold in this period." />
              <PanelBody>
                <BarList
                  items={(overview?.top_products ?? []).map((p) => ({ label: p.title, value: p.merchandise, display: money(p.merchandise), sub: `${p.units} sold`, href: `/admin/products/${p.id}` }))}
                  empty={overview ? "No sales in this period yet." : "Loading…"}
                />
              </PanelBody>
            </Panel>
            <Panel>
              <PanelHeader title="Where visitors come from" description="Visits by channel, with the orders they led to." />
              <PanelBody>
                <BarList
                  items={(overview?.channels ?? []).map((c) => ({
                    label: CHANNEL_LABEL[c.channel] ?? c.channel,
                    value: c.sessions,
                    display: `${c.sessions} visits`,
                    sub: `${c.orders} order${c.orders === 1 ? "" : "s"} · ${money(c.revenue)}`,
                  }))}
                  color="var(--viz-2)"
                  empty={overview ? "No tracked visits yet. Visits are counted for visitors who accept analytics." : "Loading…"}
                />
              </PanelBody>
            </Panel>
          </div>

          <Panel className="mt-6">
            <PanelHeader title="Recent orders" />
            {!overview ? (
              <PanelBody>
                <div className="skeleton h-24" />
              </PanelBody>
            ) : overview.recent_orders.length === 0 ? (
              <PanelBody>
                <p className="text-sm text-muted">No orders yet. They will appear here as soon as the first one is placed.</p>
              </PanelBody>
            ) : (
              <ul className="divide-y divide-line">
                {overview.recent_orders.map((o) => {
                  const status = ORDER_STATUS[o.status] ?? { label: o.status, tone: "neutral" as const };
                  return (
                    <li key={o.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 px-5 py-3 text-sm sm:grid-cols-[8rem_minmax(0,1fr)_9rem_6rem]">
                      <span className="num font-medium">{o.number}</span>
                      <span className="truncate text-muted max-sm:order-3">{o.customer_name || o.email}</span>
                      <span className="max-sm:order-4">
                        <Pill tone={status.tone}>{status.label}</Pill>
                      </span>
                      <span className="num text-right max-sm:order-2">
                        {money(o.grand_total)}
                        {o.placed_at && <span className="block text-xs text-muted">{timeAgo(o.placed_at)}</span>}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </Panel>
        </>
      )}

      {!reports && (
        <Panel>
          <PanelHeader title="Needs your attention" description="Small fixes that make the shop easier to buy from." />
          {stats === null ? (
            <PanelBody>
              <div className="skeleton h-24" />
            </PanelBody>
          ) : tasks.length === 0 ? (
            <PanelBody>
              <p className="text-sm text-muted">Nothing needs attention. Every live product has a photo, a description and stock.</p>
            </PanelBody>
          ) : (
            <ul className="divide-y divide-line">
              {tasks.map((t) => (
                <li key={t.key} className="flex items-center gap-4 px-5 py-3.5">
                  <Pill tone={t.tone} dot={false} className="num min-w-9 justify-center text-sm">
                    {t.count}
                  </Pill>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">{t.label}</p>
                    {t.hint && <p className="text-sm text-muted">{t.hint}</p>}
                  </div>
                  {t.href && (
                    <Link href={t.href} className="shrink-0 text-sm font-medium text-accent underline underline-offset-4">
                      Review
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Stock running low" description="Fewest units left first." />
          <PanelBody>
            <BarList
              items={health.low.slice(0, 6).map((p) => ({ label: p.title, value: p.stock_quantity ?? 0, display: `${p.stock_quantity} left`, href: `/admin/products/${p.id}` }))}
              max={5}
              color="var(--color-warning)"
              empty={products === null ? "Loading…" : "Everything is comfortably in stock."}
            />
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Catalog" description="Where every product stands in the publishing workflow." />
          <PanelBody>
            <StatusBar
              segments={[
                { label: "Published", value: stats?.published ?? 0, color: "var(--color-success)" },
                { label: "In review", value: stats?.in_review ?? 0, color: "var(--viz-1)" },
                { label: "Draft", value: stats?.draft ?? 0, color: "var(--color-muted)" },
                { label: "Archived", value: stats?.archived ?? 0, color: "var(--color-line)" },
              ]}
            />
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
