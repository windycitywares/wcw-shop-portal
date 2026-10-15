"use client";

import Link from "next/link";
import { Empty, Loading, ReportHeader, useReport } from "@/components/admin/analytics/common";
import { BarList } from "@/components/admin/charts/BarList";
import { fmtInt } from "@/components/admin/charts/format";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";

interface CatalogReport {
  score: number | null;
  products: number;
  checks: { key: string; label: string; count: number; weight: number; fix: string }[];
  worst: { id: number; title: string; slug: string; score: number; problems: string[] }[];
}

const scoreTone = (n: number) => (n >= 90 ? "success" : n >= 70 ? "warning" : "danger");

export default function CatalogReportPage() {
  const { data, error } = useReport<CatalogReport>("catalog", false);
  const failing = (data?.checks ?? []).filter((c) => c.count > 0).sort((a, b) => b.count * b.weight - a.count * a.weight);

  return (
    <div>
      <ReportHeader
        title="Catalog health"
        description="How complete each published listing is: photos, description, price, stock, SEO text and so on. Complete listings sell better and rank higher in search."
        exportKind="catalog"
        error={error}
      />
      <MetricStrip
        items={[
          { label: "Catalog score", value: data?.score != null ? `${data.score} / 100` : "—", hint: "Average across published products" },
          { label: "Published products", value: data ? fmtInt(data.products) : "—" },
          { label: "Listings to improve", value: data ? fmtInt(data.worst.length) : "—", hint: "Up to 20 shown below" },
        ]}
      />

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Panel>
          <PanelHeader title="Most common gaps" description="How many listings fail each check, the costliest first." />
          <PanelBody>
            {!data ? (
              <Loading />
            ) : (
              <BarList
                items={failing.map((c) => ({ label: c.label, value: c.count, display: `${c.count} listing${c.count === 1 ? "" : "s"}`, sub: c.fix }))}
                color="var(--color-warning)"
                empty={data.products === 0 ? "No published products yet." : "Every listing passes every check."}
              />
            )}
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="Listings with the most to fix" />
          {!data ? (
            <PanelBody>
              <Loading />
            </PanelBody>
          ) : data.worst.length === 0 ? (
            <PanelBody>
              <Empty>Nothing to fix.</Empty>
            </PanelBody>
          ) : (
            <ul className="divide-y divide-line">
              {data.worst.map((p) => (
                <li key={p.id} className="flex items-start gap-4 px-5 py-3">
                  <Pill tone={scoreTone(p.score)} dot={false} className="num min-w-11 justify-center">
                    {p.score}
                  </Pill>
                  <div className="min-w-0 flex-1">
                    <Link href={`/admin/products/${p.id}`} className="block truncate text-sm font-medium hover:underline">
                      {p.title}
                    </Link>
                    <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-muted">
                      {p.problems.map((x) => (
                        <li key={x}>{x}</li>
                      ))}
                    </ul>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
