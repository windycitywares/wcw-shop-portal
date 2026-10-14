export type RangePreset = "7d" | "30d" | "90d" | "mtd" | "ytd" | "custom";

/** Inclusive calendar range as ISO dates (the store's day boundaries are applied by the API). */
export interface DateRange {
  preset: RangePreset;
  from: string;
  to: string;
}

export const PRESET_LABEL: Record<RangePreset, string> = {
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  "90d": "Last 90 days",
  mtd: "This month",
  ytd: "Year to date",
  custom: "Custom range",
};

/** Local calendar date as YYYY-MM-DD (not UTC: the owner's "today" is the shop's today). */
export function isoDate(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

function addDays(d: Date, n: number) {
  const c = new Date(d);
  c.setDate(c.getDate() + n);
  return c;
}

export function presetRange(preset: Exclude<RangePreset, "custom">, today = new Date()): DateRange {
  const to = isoDate(today);
  switch (preset) {
    case "7d":
      return { preset, from: isoDate(addDays(today, -6)), to };
    case "30d":
      return { preset, from: isoDate(addDays(today, -29)), to };
    case "90d":
      return { preset, from: isoDate(addDays(today, -89)), to };
    case "mtd":
      return { preset, from: isoDate(new Date(today.getFullYear(), today.getMonth(), 1)), to };
    case "ytd":
      return { preset, from: isoDate(new Date(today.getFullYear(), 0, 1)), to };
  }
}

const dayMs = 86_400_000;
const parse = (iso: string) => new Date(`${iso}T12:00:00`);

export function rangeDays(r: { from: string; to: string }): number {
  return Math.round((parse(r.to).getTime() - parse(r.from).getTime()) / dayMs) + 1;
}

/** The same number of days immediately before `r` — what "vs previous period" compares with. */
export function previousRange(r: { from: string; to: string }): { from: string; to: string } {
  const n = rangeDays(r);
  const to = addDays(parse(r.from), -1);
  return { from: isoDate(addDays(to, -(n - 1))), to: isoDate(to) };
}

export function rangeLabel(r: DateRange): string {
  if (r.preset !== "custom") return PRESET_LABEL[r.preset];
  const f = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" });
  return `${f.format(parse(r.from))} – ${f.format(parse(r.to))}`;
}

/** Query string for the report endpoints (`/admin/reports/*`): ?start=…&end=… (inclusive store-local dates). */
export function rangeParams(r: { from: string; to: string }, extra: Record<string, string> = {}): string {
  return new URLSearchParams({ start: r.from, end: r.to, ...extra }).toString();
}
