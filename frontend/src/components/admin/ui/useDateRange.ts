"use client";

import { useCallback, useEffect, useState } from "react";
import { presetRange, type DateRange, type RangePreset } from "./dateRange";

const KEY = "wcw-admin-range";

/** The selected range, remembered for the tab so moving between reports keeps the same dates. */
export function useDateRange(initial: Exclude<RangePreset, "custom"> = "30d"): [DateRange, (r: DateRange) => void] {
  const [range, setRange] = useState<DateRange>(() => presetRange(initial));
  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(KEY) || "null") as DateRange | null;
      if (saved && saved.from && saved.to) {
        // Presets are re-anchored to today; custom ranges are kept as chosen.
        setRange(saved.preset === "custom" ? saved : presetRange(saved.preset));
      }
    } catch {
      /* storage unavailable */
    }
  }, []);
  const set = useCallback((r: DateRange) => {
    setRange(r);
    try {
      sessionStorage.setItem(KEY, JSON.stringify(r));
    } catch {
      /* ignore */
    }
  }, []);
  return [range, set];
}
