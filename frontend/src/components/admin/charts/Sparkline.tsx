import { cn } from "@/lib/utils";

/**
 * A tiny trend line for a figure. It stretches to the room it is given (up to `width`) and never spills past
 * its box: the drawing is scaled with the box, while the line and the end dot keep their thickness and shape
 * (non-scaling strokes; the dot is a zero-length round-capped stroke, so it stays a circle at any width).
 */
export function Sparkline({
  values,
  width = 88,
  height = 28,
  color = "var(--color-accent)",
  className,
}: {
  values: number[];
  /** Widest it gets; it shrinks when the space is narrower. */
  width?: number;
  height?: number;
  color?: string;
  className?: string;
}) {
  const box = { maxWidth: width, height };
  if (values.length < 2) return <span aria-hidden="true" className={cn("block min-w-0 flex-1", className)} style={box} />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = 4;
  const pts = values.map((v, i) => [pad + (i / (values.length - 1)) * (width - pad * 2), pad + (1 - (v - min) / span) * (height - pad * 2)] as const);
  const d = pts.map(([a, b], i) => `${i ? "L" : "M"}${a.toFixed(1)} ${b.toFixed(1)}`).join(" ");
  const [lx, ly] = pts[pts.length - 1];
  return (
    <svg
      aria-hidden="true"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={cn("block min-w-0 flex-1 overflow-visible", className)}
      style={box}
    >
      <path d={d} fill="none" stroke={color} strokeWidth={1.75} strokeLinejoin="round" strokeLinecap="round" opacity={0.9} vectorEffect="non-scaling-stroke" />
      <path d={`M${lx.toFixed(1)} ${ly.toFixed(1)}h0`} stroke="var(--color-surface)" strokeWidth={8} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      <path d={`M${lx.toFixed(1)} ${ly.toFixed(1)}h0`} stroke={color} strokeWidth={6} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
