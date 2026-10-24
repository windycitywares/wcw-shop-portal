"use client";

import { RangeContext, ReportBar } from "@/components/admin/analytics/common";
import { useDateRange } from "@/components/admin/ui/useDateRange";

/** Every analytics page shares one date range and one report bar. */
export default function AnalyticsLayout({ children }: { children: React.ReactNode }) {
  const range = useDateRange("30d");
  return (
    <RangeContext.Provider value={range}>
      <ReportBar />
      {children}
    </RangeContext.Provider>
  );
}
