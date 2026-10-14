import { cn } from "@/lib/utils";
import { fmtInt, pct } from "./format";

export interface FunnelStage {
  label: string;
  value: number;
  /** Plain-language hint under the label. */
  hint?: string;
}

/** Ordinal ramp: the theme accent from 45% to 100% (lightest still ≥ 2:1 on the panel). */
const step = (i: number, n: number) => `color-mix(in oklab, var(--color-accent) ${n <= 1 ? 100 : Math.round(45 + (55 * i) / (n - 1))}%, var(--color-surface))`;

/** Shopper journey: each stage as a bar (relative to the first), with the share who continued. */
export function Funnel({ stages, className }: { stages: FunnelStage[]; className?: string }) {
  const first = Math.max(stages[0]?.value ?? 0, 1);
  return (
    <ol className={cn("space-y-3", className)}>
      {stages.map((s, i) => {
        const prev = i > 0 ? stages[i - 1].value : null;
        const keep = prev ? s.value / prev : null;
        return (
          <li key={s.label}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="font-medium">{s.label}</span>
              <span className="num">
                <span className="font-semibold">{fmtInt(s.value)}</span>
                {keep != null && (
                  <span className="ml-2 text-muted">
                    {pct(keep, keep < 0.1 ? 1 : 0)} <span className="sr-only">continued from {stages[i - 1].label}</span>
                  </span>
                )}
              </span>
            </div>
            <div className="mt-1.5 h-5 rounded-[3px] bg-sand" role="presentation">
              <div className="h-full rounded-[3px]" style={{ width: `${Math.max(0.8, (s.value / first) * 100)}%`, background: step(i, stages.length) }} />
            </div>
            {s.hint && <p className="mt-1 text-xs text-muted">{s.hint}</p>}
          </li>
        );
      })}
    </ol>
  );
}
