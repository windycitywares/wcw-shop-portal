"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Icon } from "./Icon";
import { Popover } from "@/components/ui/Popover";
import { PRESET_LABEL, isoDate, presetRange, rangeLabel, type DateRange, type RangePreset } from "./dateRange";

const PRESETS: Exclude<RangePreset, "custom">[] = ["7d", "30d", "90d", "mtd", "ytd"];

/**
 * Date range filter: presets as rows (nobody wants a calendar grid for "last 30 days"), the custom
 * range tucked below a hairline. Sits in the single filter row above the content it scopes.
 */
export function DateRangePicker({ value, onChange }: { value: DateRange; onChange: (r: DateRange) => void }) {
  const [from, setFrom] = useState(value.from);
  const [to, setTo] = useState(value.to);
  const today = isoDate(new Date());
  const invalid = !from || !to || from > to;
  return (
    <Popover
      align="left"
      label={`Date range: ${rangeLabel(value)}`}
      trigger={
        <>
          <Icon name="calendar" className="size-4 text-muted" />
          <span>{rangeLabel(value)}</span>
          <Icon name="chevronDown" className="size-4 text-muted" />
        </>
      }
      panelClassName="w-64"
    >
      {(close) => (
        <div>
          <ul>
            {PRESETS.map((p) => {
              const on = value.preset === p;
              return (
                <li key={p}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(presetRange(p));
                      close();
                    }}
                    className={cn("flex w-full items-center justify-between rounded-[var(--radius-control)] px-3 py-2 text-left text-sm hover:bg-sand", on && "font-semibold")}
                  >
                    {PRESET_LABEL[p]}
                    {on && <Icon name="check" className="size-4 text-accent" strokeWidth={2.4} />}
                  </button>
                </li>
              );
            })}
          </ul>
          <form
            className="mt-1.5 space-y-2 border-t border-line px-3 pb-2 pt-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (invalid) return;
              onChange({ preset: "custom", from, to });
              close();
            }}
          >
            <p className="text-xs font-medium text-muted">Custom range</p>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs text-muted">
                From
                <input type="date" value={from} max={today} onChange={(e) => setFrom(e.target.value)} className="mt-0.5 w-full rounded-[var(--radius-control)] border border-line bg-surface px-2 py-1.5 text-sm text-ink" />
              </label>
              <label className="text-xs text-muted">
                To
                <input type="date" value={to} max={today} onChange={(e) => setTo(e.target.value)} className="mt-0.5 w-full rounded-[var(--radius-control)] border border-line bg-surface px-2 py-1.5 text-sm text-ink" />
              </label>
            </div>
            <Button type="submit" size="sm" className="w-full" disabled={invalid}>
              Apply range
            </Button>
          </form>
        </div>
      )}
    </Popover>
  );
}
