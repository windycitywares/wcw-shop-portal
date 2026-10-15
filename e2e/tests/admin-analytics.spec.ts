import { expect, test } from "@playwright/test";
import { adminReady, adminState, watch } from "./support";

test.use({ storageState: adminState });

test("the sales report loads and downloads as a spreadsheet", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/admin/analytics/sales");
  await adminReady(page);
  await expect(page.getByRole("heading", { name: "Revenue over time" })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download CSV" }).click();
  expect((await download).suggestedFilename()).toMatch(/^wcw-sales-\d{4}-\d{2}-\d{2}-to-\d{4}-\d{2}-\d{2}\.csv$/);
  await expect(page.getByText("Downloaded")).toBeVisible();
  seen.expectClean();
});

test("the report links move between reports and mark the current one", async ({ page }) => {
  await page.goto("/admin/analytics");
  await adminReady(page);
  const reports = page.getByRole("navigation", { name: "Reports" });
  await expect(reports.getByRole("link", { name: "Suggestions" })).toHaveAttribute("aria-current", "page");
  await reports.getByRole("link", { name: "Products" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Product performance" })).toBeVisible();
  await expect(reports.getByRole("link", { name: "Products" })).toHaveAttribute("aria-current", "page");
});
