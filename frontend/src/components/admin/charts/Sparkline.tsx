import { cn } from "@/lib/utils";

/** Tiny trend line for tiles. Decorative: the figure beside it carries the value. */
export function Sparkline({
  values,
  width = 88,
  height = 28,
  color = "var(--color-accent)",
  className,
}: {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
  className?: string;
}) {
  if (values.length < 2) return <span aria-hidden="true" className={className} style={{ width, height, display: "inline-block" }} />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = 3;
  const pts = values.map((v, i) => [pad + (i / (values.length - 1)) * (width - pad * 2), pad + (1 - (v - min) / span) * (height - pad * 2)] as const);
  const d = pts.map(([a, b], i) => `${i ? "L" : "M"}${a.toFixed(1)} ${b.toFixed(1)}`).join(" ");
  const [lx, ly] = pts[pts.length - 1];
  return (
    <svg aria-hidden="true" width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={cn("shrink-0 overflow-visible", className)}>
      <path d={d} fill="none" stroke={color} strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" opacity={0.9} />
      <circle cx={lx} cy={ly} r={3} fill={color} stroke="var(--color-surface)" strokeWidth={1.5} />
    </svg>
  );
}
