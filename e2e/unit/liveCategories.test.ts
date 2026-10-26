import assert from "node:assert/strict";
import { test } from "node:test";
import { DEFAULT_PREFS, categoryOf, plan } from "../../frontend/src/lib/liveCategories";

test("every live event kind has a setting", () => {
  for (const kind of ["order.new", "order.paid", "order.refund", "order.status", "message.new", "customer.new", "subscriber.new", "subscriber.left", "review.new", "stock_request.new", "product.changed", "backup.failed"]) {
    assert.notEqual(categoryOf(kind), null, kind);
  }
  assert.equal(categoryOf("order.paid"), "orders_payments");
  assert.equal(categoryOf("subscriber.left"), "newsletter");
  assert.equal(categoryOf("something.else"), null);
});

test("by default new orders pop up with a sound, sign-ups stay quiet", () => {
  const p = plan([{ kind: "order.new" }, { kind: "subscriber.new" }], DEFAULT_PREFS);
  assert.deepEqual(p.popups.map((e) => e.kind), ["order.new"]);
  assert.equal(p.sound, true);
  assert.deepEqual(p.desktop, []);
});

test("a person's own choices decide, and volume 0 means no sound", () => {
  const prefs = structuredClone(DEFAULT_PREFS);
  prefs.categories.newsletter = { popup: true, sound: true, desktop: true };
  prefs.volume = 0;
  const p = plan([{ kind: "subscriber.new" }], prefs);
  assert.equal(p.popups.length, 1);
  assert.equal(p.sound, false);
  assert.equal(p.desktop.length, 1);
});
