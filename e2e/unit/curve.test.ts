import assert from "node:assert/strict";
import { test } from "node:test";
import { smoothPath } from "../../frontend/src/components/admin/charts/curve";

const nums = (d: string) => (d.match(/-?\d+(\.\d+)?/g) ?? []).map(Number);

test("short runs are a dot or a straight line", () => {
  assert.equal(smoothPath([]), "");
  assert.equal(smoothPath([[0, 10]]), "M0.0 10.0");
  assert.equal(smoothPath([[0, 10], [10, 20]]), "M0.0 10.0 L10.0 20.0");
});

test("the curve passes through every point", () => {
  const pts = [[0, 50], [10, 20], [20, 40], [30, 10]] as const;
  const d = smoothPath(pts);
  assert.ok(d.startsWith("M0.0 50.0"));
  for (const [x, y] of pts.slice(1)) assert.ok(d.includes(`${x.toFixed(1)} ${y.toFixed(1)}`), `missing ${x},${y}`);
});

test("a flat run stays flat and nothing overshoots the data", () => {
  // y grows downward in SVG: 100 is the zero line here. A zero between two values must not dip below it.
  const pts = [[0, 100], [10, 100], [20, 100], [30, 20], [40, 100]] as const;
  const d = smoothPath(pts);
  const ys = nums(d).filter((_, i) => i % 2 === 1);
  assert.ok(Math.max(...ys) <= 100.0001, `went below the axis: ${Math.max(...ys)}`);
  assert.ok(Math.min(...ys) >= 19.9999, `rose above the peak: ${Math.min(...ys)}`);
  // first segment (both ends at 100) has flat control points
  assert.ok(d.includes("C3.3 100.0 6.7 100.0 10.0 100.0"));
});
