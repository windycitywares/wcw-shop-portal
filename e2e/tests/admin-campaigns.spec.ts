import { expect, test } from "@playwright/test";
import { adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("campaigns are view-only here and point to the CRM", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/admin/campaigns");
  await adminReady(page);
  await expect(page.getByTestId("crm-notice")).toContainText("managed in the CRM");
  await expect(page.getByRole("link", { name: /Write, send and track campaigns in the CRM/ })).toHaveAttribute("href", /\/campaigns$/);
  await expect(page.getByRole("button", { name: "New campaign" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Send / })).toHaveCount(0);
  seen.expectClean();
});

test("customers and abandoned carts open with their summaries", async ({ page }) => {
  await page.goto("/admin/customers");
  await adminReady(page);
  await expect(page.getByRole("list", { name: "Customer groups" })).toBeVisible();
  await page.goto("/admin/carts");
  await adminReady(page);
  await expect(page.getByText("Carts started")).toBeVisible();
});
