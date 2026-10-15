"use client";

import { useState } from "react";
import { InsightList, Loading, ReportHeader, useReport, type RangeInfo } from "@/components/admin/analytics/common";
import { timeAgo } from "@/components/admin/charts/format";
import { SEVERITY, type Insight } from "@/components/admin/reports";
import { Panel, PanelBody } from "@/components/admin/ui/Panel";
import { Tabs } from "@/components/admin/ui/Tabs";

interface Suggestions {
  range: RangeInfo;
  items: Insight[];
  counts: Record<Insight["severity"], number>;
  generated_at: string;
}

type Filter = "all" | Insight["severity"];
const ORDER: Insight["severity"][] = ["critical", "warning", "opportunity", "info", "success"];

/** Every recommendation the rules found for the period, most urgent first. */
export default function AnalyticsSuggestions() {
  const { range, setRange, data, error } = useReport<Suggestions>("suggestions");
  const [filter, setFilter] = useState<Filter>("all");
  const items = (data?.items ?? []).filter((i) => filter === "all" || i.severity === filter);

  return (
    <div>
      <ReportHeader
        title="Analytics"
        description="Suggestions come from simple rules over this period's numbers. They stay quiet until there is enough data to mean something, so a new shop sees few."
        range={range}
        onRange={setRange}
        error={error}
      />
      <Panel>
        <div className="px-4 pt-3">
          <Tabs<Filter>
            label="Filter suggestions"
            value={filter}
            onChange={setFilter}
            tabs={[
              { id: "all", label: "All", count: data?.items.length },
              ...ORDER.map((s) => ({ id: s, label: SEVERITY[s].label, count: data?.counts[s] })),
            ]}
          />
        </div>
        {data === null ? (
          <PanelBody>
            <Loading />
          </PanelBody>
        ) : (
          <InsightList
            items={items}
            empty={filter === "all" ? "No suggestions for this period. They appear once there are enough visits and orders to judge." : "Nothing in this group."}
          />
        )}
        {data && <p className="border-t border-line px-5 py-3 text-xs text-muted">Worked out {timeAgo(data.generated_at)}.</p>}
      </Panel>
    </div>
  );
}
