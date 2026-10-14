import { cn } from "@/lib/utils";

export interface Segment {
  label: string;
  value: number;
  /** CSS colour. */
  color: string;
  href?: string;
}

/**
 * One stacked bar for "how many of each" (products by status). 2px gaps between segments, a legend that
 * doubles as the readout (label + count), so no colour has to be matched by eye.
 */
export function StatusBar({ segments, className }: { segments: Segment[]; className?: string }) {
  const total = segments.reduce((n, s) => n + s.value, 0);
  return (
    <div className={className}>
      <div className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-sand" role="img" aria-label={segments.map((s) => `${s.label}: ${s.value}`).join(", ")}>
        {segments
          .filter((s) => s.value > 0)
          .map((s) => (
            <span key={s.label} style={{ width: `${(s.value / Math.max(total, 1)) * 100}%`, background: s.color }} className="first:rounded-l-full last:rounded-r-full" />
          ))}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-1.5 text-sm">
        {segments.map((s) => (
          <li key={s.label} className={cn("flex items-center gap-2", s.value === 0 && "[&>span:first-child]:opacity-40")}>
            <span aria-hidden="true" className="size-2.5 rounded-[3px]" style={{ background: s.color }} />
            <span className="text-muted">{s.label}</span>
            <span className="num font-semibold">{s.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
