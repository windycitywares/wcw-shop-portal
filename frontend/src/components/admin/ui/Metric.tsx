import Link from "next/link";
import { cn } from "@/lib/utils";
import { Sparkline } from "../charts/Sparkline";
import { Icon, type IconName } from "./Icon";

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
  /** A small round icon beside the label. */
  icon?: IconName;
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
        {items.map((m) => (
          // One group per figure, with dt/dd as direct children (what <dl> requires). A linked figure uses a
          // stretched link inside the <dt>, so the whole cell is clickable.
          <div
            key={m.label}
            className={cn("relative min-w-0 border-l border-t border-line px-5 py-4", m.href && "hover:bg-canvas has-[a:focus-visible]:bg-canvas")}
          >
            <dt className="flex items-start justify-between gap-2 text-sm text-muted">
              <span className="min-w-0">
                {m.href ? (
                  <Link href={m.href} className="after:absolute after:inset-0 hover:text-ink hover:underline">
                    {m.label}
                  </Link>
                ) : (
                  m.label
                )}
              </span>
              {m.icon && (
                <span aria-hidden="true" className="-mr-1 -mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-accent-soft text-accent">
                  <Icon name={m.icon} className="size-4" />
                </span>
              )}
            </dt>
            {/* The figure keeps its width; the sparkline takes what is left (up to 88px) and stays inside the cell. */}
            <dd className="flex min-w-0 items-end justify-between gap-3 overflow-hidden py-1 pr-1">
              <span className="num shrink-0 text-[1.625rem] font-semibold leading-none tracking-tight">{m.value}</span>
              {m.spark && <Sparkline values={m.spark} className="ml-auto" />}
            </dd>
            {m.change !== undefined && (
              <dd className="mt-2">
                <Delta change={m.change} good={m.good} label={compareLabel} />
              </dd>
            )}
            {m.hint && <dd className="mt-1 text-xs text-muted">{m.hint}</dd>}
          </div>
        ))}
      </dl>
    </div>
  );
}
