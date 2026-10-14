import assert from "node:assert/strict";
import { test } from "node:test";
import { isoDate, presetRange, previousRange, rangeDays, rangeLabel, rangeParams } from "../../frontend/src/components/admin/ui/dateRange";

// Local noon, so the test result doesn't depend on the machine's time zone offset.
const today = new Date(2026, 9, 14, 12, 0, 0); // Wed 14 Oct 2026

test("isoDate uses the local calendar day", () => {
  assert.equal(isoDate(new Date(2026, 0, 5, 23, 59)), "2026-01-05");
  assert.equal(isoDate(new Date(2026, 11, 31, 0, 1)), "2026-12-31");
});

test("presets are inclusive and end today", () => {
  assert.deepEqual(presetRange("7d", today), { preset: "7d", from: "2026-10-08", to: "2026-10-14" });
  assert.deepEqual(presetRange("30d", today), { preset: "30d", from: "2026-09-15", to: "2026-10-14" });
  assert.deepEqual(presetRange("mtd", today), { preset: "mtd", from: "2026-10-01", to: "2026-10-14" });
  assert.deepEqual(presetRange("ytd", today), { preset: "ytd", from: "2026-01-01", to: "2026-10-14" });
  assert.equal(rangeDays(presetRange("30d", today)), 30);
  assert.equal(rangeDays(presetRange("90d", today)), 90);
});

test("the previous period has the same length and ends the day before", () => {
  const r = presetRange("7d", today);
  assert.deepEqual(previousRange(r), { from: "2026-10-01", to: "2026-10-07" });
  assert.equal(rangeDays(previousRange(r)), 7);
  const month = { from: "2026-03-01", to: "2026-03-31" };
  assert.deepEqual(previousRange(month), { from: "2026-01-29", to: "2026-02-28" });
});

test("a range across the daylight-saving change still counts whole days", () => {
  assert.equal(rangeDays({ from: "2026-03-01", to: "2026-03-31" }), 31);
  assert.equal(rangeDays({ from: "2026-10-25", to: "2026-11-02" }), 9);
});

test("labels and query strings", () => {
  assert.equal(rangeLabel(presetRange("30d", today)), "Last 30 days");
  assert.equal(rangeLabel({ preset: "custom", from: "2026-10-01", to: "2026-10-14" }), "Oct 1, 2026 – Oct 14, 2026");
  assert.equal(rangeParams({ from: "2026-10-01", to: "2026-10-14" }), "from=2026-10-01&to=2026-10-14");
  assert.equal(rangeParams({ from: "2026-10-01", to: "2026-10-14" }, { by: "day" }), "from=2026-10-01&to=2026-10-14&by=day");
});
