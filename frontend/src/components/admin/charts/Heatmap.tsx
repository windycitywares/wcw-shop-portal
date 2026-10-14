import { cn } from "@/lib/utils";

/**
 * Table-shaped heatmap (cohort retention, day × hour). Cells are real table cells, so the grid is
 * readable by screen readers; the colour is one hue, light → dark, with text that flips for contrast.
 */
export function Heatmap({
  rowHeader,
  columns,
  rows,
  format = (v) => `${Math.round(v * 100)}%`,
  caption,
  className,
}: {
  rowHeader: string;
  columns: string[];
  rows: { label: string; sub?: string; cells: (number | null)[] }[];
  /** Cell text for a 0–1 value. */
  format?: (v: number) => string;
  caption: string;
  className?: string;
}) {
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full border-separate border-spacing-[2px] text-xs">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" className="px-2 py-1 text-left font-medium text-muted">
              {rowHeader}
            </th>
            {columns.map((c) => (
              <th key={c} scope="col" className="px-1 py-1 text-center font-medium text-muted">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row" className="whitespace-nowrap px-2 py-1 text-left font-medium">
                {r.label}
                {r.sub && <span className="ml-1.5 font-normal text-muted">{r.sub}</span>}
              </th>
              {columns.map((c, i) => {
                const v = r.cells[i];
                if (v == null) return <td key={c} className="rounded-[3px] bg-sand/50" />;
                const strength = Math.max(0, Math.min(1, v));
                return (
                  <td
                    key={c}
                    className="num min-w-10 rounded-[3px] px-1 py-1.5 text-center font-medium"
                    style={{
                      background: `color-mix(in oklab, var(--color-accent) ${Math.round(8 + strength * 82)}%, var(--color-surface))`,
                      color: strength > 0.45 ? "var(--color-on-accent)" : "var(--color-ink)",
                    }}
                  >
                    {format(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
