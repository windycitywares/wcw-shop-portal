import assert from "node:assert/strict";
import { test } from "node:test";
import { compact, dayLabel, fmtInt, labelIndices, money, niceTicks, pct, timeAgo } from "../../frontend/src/components/admin/charts/format";

test("compact keeps small numbers whole and shortens large ones", () => {
  assert.equal(compact(0), "0");
  assert.equal(compact(9999), "9,999");
  assert.equal(compact(12_900), "12.9K");
  assert.equal(compact(4_200_000), "4.2M");
  assert.equal(fmtInt(1284), "1,284");
});

test("money shows cents for small amounts and whole dollars for big ones", () => {
  assert.equal(money(68), "$68.00");
  assert.equal(money(1284.5), "$1,285");
  assert.equal(money(1284.5, { cents: true }), "$1,284.50");
  assert.equal(money(125_000, { compact: true }), "$125K");
  assert.equal(money(-12.5), "-$12.50");
});

test("pct turns a fraction into a tidy percentage", () => {
  assert.equal(pct(0.123), "12.3%");
  assert.equal(pct(0.5), "50%");
  assert.equal(pct(0), "0%");
  assert.equal(pct(0.0345, 2), "3.45%");
});

test("dayLabel uses the date as written, whatever the time zone", () => {
  assert.equal(dayLabel("2026-10-14"), "Oct 14");
  assert.equal(dayLabel("2026-10-14", "long"), "Wed, Oct 14");
  assert.equal(dayLabel("2026-01-01"), "Jan 1");
});

test("timeAgo reads naturally", () => {
  const now = Date.parse("2026-10-14T12:00:00Z");
  assert.equal(timeAgo("2026-10-14T11:59:40Z", now), "just now");
  assert.equal(timeAgo("2026-10-14T11:15:00Z", now), "45 min ago");
  assert.equal(timeAgo("2026-10-14T09:00:00Z", now), "3 hr ago");
  assert.equal(timeAgo("2026-10-13T12:00:00Z", now), "1 day ago");
  assert.equal(timeAgo("2026-10-10T12:00:00Z", now), "4 days ago");
  assert.equal(timeAgo("2026-08-01T12:00:00Z", now), "Aug 1");
});

test("niceTicks covers the data with round numbers and includes zero", () => {
  const t = niceTicks(0, 87);
  assert.equal(t[0], 0);
  assert.ok(t.at(-1)! >= 87);
  for (const v of t) assert.equal(v % 5, 0);
  assert.deepEqual(niceTicks(0, 0), [0, 1, 2, 3, 4]);
  assert.deepEqual(niceTicks(Number.NaN, 5), [0, 1]);
  const steps = t.slice(1).map((v, i) => v - t[i]);
  assert.ok(steps.every((s) => s === steps[0]), "ticks are evenly spaced");
});

test("labelIndices always includes the first and last label", () => {
  assert.deepEqual(labelIndices(0, 5), []);
  assert.deepEqual(labelIndices(3, 5), [0, 1, 2]);
  const idx = labelIndices(30, 6);
  assert.equal(idx[0], 0);
  assert.equal(idx.at(-1), 29);
  assert.ok(idx.length <= 6);
});
