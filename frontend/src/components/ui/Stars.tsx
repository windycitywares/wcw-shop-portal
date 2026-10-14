import { cn } from "@/lib/utils";

/** Read-only star rating: five stars filled to the average, with the full sentence for screen readers. */
export function Stars({ rating, count, label, className }: { rating: number; count?: number; label: string; className?: string }) {
  const pct = Math.max(0, Math.min(100, (rating / 5) * 100));
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span aria-hidden="true" className="relative inline-block leading-none tracking-[0.1em]">
        <span className="text-line">★★★★★</span>
        <span className="absolute inset-0 overflow-hidden whitespace-nowrap text-accent" style={{ width: `${pct}%` }}>
          ★★★★★
        </span>
      </span>
      {count != null && (
        <span aria-hidden="true" className="text-xs text-muted tabular-nums">
          ({count})
        </span>
      )}
      <span className="sr-only">{label}</span>
    </span>
  );
}
