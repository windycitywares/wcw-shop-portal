"use client";

import { Loading, ReportHeader, useReport, type RangeInfo } from "@/components/admin/analytics/common";
import { BarList } from "@/components/admin/charts/BarList";
import { fmtInt } from "@/components/admin/charts/format";
import { rate } from "@/components/admin/reports";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { MetricStrip } from "@/components/admin/ui/Metric";
import { Panel, PanelBody, PanelHeader } from "@/components/admin/ui/Panel";

interface Term {
  term: string;
  searches: number;
  avg_results: number;
  no_results: number;
}
interface BehaviorReport {
  range: RangeInfo;
  top_pages: { path: string; views: number; sessions: number }[];
  events: { type: string; label: string; events: number; sessions: number }[];
  depth: { band: string; sessions: number; share: number | null }[];
  search: {
    searches: number;
    no_results: number;
    no_result_rate: number | null;
    terms: Term[];
    searchers: number;
    searcher_conversion: number | null;
    other_conversion: number | null;
  };
}

export default function BehaviorReportPage() {
  const { range, setRange, data, error } = useReport<BehaviorReport>("behavior");
  const s = data?.search;
  const termCols: Column<Term>[] = [
    { key: "term", header: "Search", cell: (t) => <span className="font-medium">{t.term}</span> },
    { key: "searches", header: "Times", align: "right", cell: (t) => <span className="num">{fmtInt(t.searches)}</span> },
    { key: "results", header: "Avg. results", align: "right", hide: "md", cell: (t) => <span className="num">{t.avg_results}</span> },
    {
      key: "none",
      header: "Found nothing",
      align: "right",
      cell: (t) => <span className={t.no_results > 0 ? "num font-medium text-danger" : "num text-muted"}>{fmtInt(t.no_results)}</span>,
    },
  ];

  return (
    <div>
      <ReportHeader
        title="Visitor behavior"
        description="What visitors look at, search for and do on the site. Only visitors who accepted analytics are counted."
        range={range}
        onRange={setRange}
        error={error}
      />

      <MetricStrip
        items={[
          { label: "Searches", value: s ? fmtInt(s.searches) : "—" },
          { label: "Found nothing", value: s ? rate(s.no_result_rate, 0) : "—", hint: "Searches with no results" },
          { label: "Searchers who ordered", value: s ? rate(s.searcher_conversion) : "—", hint: s ? `${fmtInt(s.searchers)} visits used search` : undefined },
          { label: "Other visits that ordered", value: s ? rate(s.other_conversion) : "—", hint: "Visits that didn't search" },
        ]}
      />

      <Panel className="mt-6">
        <PanelHeader
          title="What people search for"
          description="Searches that find nothing are products people want and can't find: add the word to a product's tags or description, or consider making it."
        />
        <DataTable columns={termCols} rows={s?.terms ?? null} rowKey={(t) => t.term} caption="Search terms" empty="No searches in this period yet." />
      </Panel>

      <div className="mt-6 grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Most viewed pages" />
          <PanelBody>
            {data ? (
              <BarList
                items={data.top_pages.map((p) => ({ label: p.path, value: p.views, display: `${fmtInt(p.views)} views`, sub: `${fmtInt(p.sessions)} visits` }))}
                empty="No tracked page views yet."
              />
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
        <Panel>
          <PanelHeader title="How far visitors go" description="Pages viewed per visit." />
          <PanelBody>
            {data ? (
              <BarList
                items={data.depth.map((d) => ({ label: d.band, value: d.sessions, display: rate(d.share, 0), sub: `${fmtInt(d.sessions)} visits` }))}
                color="var(--viz-2)"
                empty="No tracked visits yet."
              />
            ) : (
              <Loading />
            )}
          </PanelBody>
        </Panel>
      </div>

      <Panel className="mt-6">
        <PanelHeader title="What visitors do" description="Each action, and how many visits did it at least once." />
        <PanelBody>
          {data ? (
            <BarList
              items={data.events.map((e) => ({ label: e.label, value: e.sessions, display: `${fmtInt(e.sessions)} visits`, sub: `${fmtInt(e.events)} times` }))}
              color="var(--viz-3)"
              empty="Nothing recorded yet."
            />
          ) : (
            <Loading />
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
