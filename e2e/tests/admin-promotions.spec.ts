import { expect, test } from "@playwright/test";
import { adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("a sale, a coupon and a batch of codes can be created", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/admin/promotions");
  await adminReady(page);

  // A sale scheduled far in the future, so tests running at the same time still see normal prices.
  const saleName = unique("Sale");
  await page.getByRole("button", { name: "New sale" }).click();
  const sale = page.getByRole("dialog", { name: "New sale" });
  await sale.getByLabel("Name", { exact: true }).fill(saleName);
  await sale.getByLabel("Percent off").fill("15");
  await sale.getByLabel("Starts (optional)").fill("2099-01-01T09:00");
  await sale.getByRole("button", { name: "Create sale" }).click();
  const row = page.getByRole("row").filter({ hasText: saleName });
  await expect(row.getByText("Scheduled")).toBeVisible();
  await row.getByRole("button", { name: `Pause ${saleName}` }).click();
  await expect(page.getByText("Sale paused")).toBeVisible();

  // A single coupon with a chosen code.
  await page.getByRole("tab", { name: "Coupons" }).click();
  const code = unique("SAVE").replace(/[^A-Za-z0-9]/g, "").toUpperCase().slice(0, 20);
  await page.getByRole("button", { name: "New coupon" }).click();
  const single = page.getByRole("dialog", { name: "New coupon" });
  await single.getByLabel("Code", { exact: true }).fill(code);
  await single.getByRole("button", { name: "Create coupon" }).click();
  await expect(page.getByRole("button", { name: code, exact: true })).toBeVisible();

  // A batch of codes for a campaign.
  const campaign = unique("e2e-batch");
  await page.getByRole("button", { name: "Generate codes" }).click();
  const bulk = page.getByRole("dialog", { name: "Generate codes" });
  await bulk.getByLabel("Campaign", { exact: true }).fill(campaign);
  await bulk.getByLabel("How many codes").fill("5");
  await bulk.getByLabel("Prefix (optional)").fill("EE");
  await bulk.getByRole("button", { name: "Generate codes" }).click();
  await expect(page.getByText(`5 codes created for “${campaign}”`)).toBeVisible();
  seen.expectClean();
});
