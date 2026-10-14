import Link from "next/link";
import { cn } from "@/lib/utils";
import { Sparkline } from "../charts/Sparkline";
import { Icon } from "./Icon";

/**
 * Change versus the previous period. `good` says which direction is good (more orders: up; more refunds:
 * down), so the colour means "better/worse", and an arrow + words mean "up/down".
 */
export function Delta({
  change,
  good = "up",
  label = "vs previous period",
  className,
}: {
  /** Fractional change: 0.12 = +12%. null = nothing to compare. */
  change: number | null | undefined;
  good?: "up" | "down";
  label?: string;
  className?: string;
}) {
  if (change == null || !isFinite(change)) return <span className={cn("text-xs text-muted", className)}>No earlier data</span>;
  const flat = Math.abs(change) < 0.0005;
  const up = change > 0;
  const better = flat ? null : up === (good === "up");
  const tone = flat ? "text-muted" : better ? "text-success" : "text-danger";
  const shown = `${Math.abs(change * 100).toFixed(Math.abs(change) < 0.1 ? 1 : 0)}%`;
  return (
    <span className={cn("inline-flex items-center gap-1 text-xs", className)}>
      <span className={cn("inline-flex items-center gap-0.5 font-semibold", tone)}>
        {!flat && <Icon name={up ? "arrowUp" : "arrowDown"} className="size-3.5" strokeWidth={2.2} />}
        <span className="num">{flat ? "0%" : shown}</span>
        <span className="sr-only">{flat ? "unchanged" : up ? "up" : "down"}</span>
      </span>
      <span className="text-muted">{label}</span>
    </span>
  );
}

export interface MetricItem {
  label: string;
  /** Already formatted: "$4,210", "3.2%". */
  value: string;
  change?: number | null;
  good?: "up" | "down";
  /** One-line plain-English explanation, shown under the figure. */
  hint?: string;
  spark?: number[];
  href?: string;
}

/**
 * The key numbers as one ruled strip (not a row of separate cards): label, figure, change, sparkline.
 * Wraps to two columns on phones.
 */
export function MetricStrip({ items, compareLabel, className }: { items: MetricItem[]; compareLabel?: string; className?: string }) {
  return (
    // Hairline dividers without double borders: every cell draws its top/left edge, and the grid is
    // shifted 1px up/left so the outer edges are clipped by the wrapper's own border.
    <div className={cn("overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface", className)}>
      <dl
        className="-ml-px -mt-px grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-[repeat(var(--cols),minmax(0,1fr))]"
        style={{ ["--cols" as string]: items.length }}
      >
        {items.map((m) => {
          const body = (
            <>
              <dt className="text-sm text-muted">{m.label}</dt>
              <dd className="mt-1 flex items-end justify-between gap-2">
                <span className="num text-[1.625rem] font-semibold leading-none tracking-tight">{m.value}</span>
                {m.spark && <Sparkline values={m.spark} />}
              </dd>
              {m.change !== undefined && (
                <dd className="mt-2">
                  <Delta change={m.change} good={m.good} label={compareLabel} />
                </dd>
              )}
              {m.hint && <dd className="mt-1 text-xs text-muted">{m.hint}</dd>}
            </>
          );
          return (
            <div key={m.label} className="border-l border-t border-line">
              {m.href ? (
                <Link href={m.href} className="block h-full px-5 py-4 hover:bg-canvas">
                  {body}
                </Link>
              ) : (
                <div className="h-full px-5 py-4">{body}</div>
              )}
            </div>
          );
        })}
      </dl>
    </div>
  );
}
