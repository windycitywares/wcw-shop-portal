import { expect, test } from "@playwright/test";
import { adminApi, adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("a shopper who signed up without ordering is in Customers and their account can be switched off", async ({ page }) => {
  const api = await adminApi();
  const email = `${unique("signup")}@example.com`;
  const created = await api.post("users", { data: { email, password: "Customer-pass-123", full_name: "E2E Signup", role: "customer" } });
  expect(created.ok(), await created.text()).toBeTruthy();
  await api.dispose();

  const seen = watch(page);
  await page.goto(`/admin/customers?q=${encodeURIComponent(email)}`);
  await adminReady(page);
  const row = page.getByRole("row").filter({ hasText: email });
  await expect(row).toHaveCount(1);
  await expect(row.getByText("Signed up, no order yet")).toBeVisible();
  await expect(row.getByText("Account", { exact: true })).toBeVisible();

  await row.getByRole("button", { name: "E2E Signup" }).click();
  const detail = page.getByRole("dialog", { name: "E2E Signup" });
  await detail.getByRole("button", { name: "Switch account off" }).click();
  await page.getByRole("dialog", { name: "Switch this account off?" }).getByRole("button", { name: "Switch account off" }).click();
  await expect(page.locator("[aria-live=polite]").getByText("Account switched off", { exact: true })).toBeVisible();
  await expect(row.getByText("Switched off", { exact: true })).toBeVisible();

  // And back on, from the profile again.
  await row.getByRole("button", { name: "E2E Signup" }).click();
  await detail.getByRole("button", { name: "Switch account on" }).click();
  await page.getByRole("dialog", { name: "Switch this account on?" }).getByRole("button", { name: "Switch account on" }).click();
  await expect(row.getByText("Account", { exact: true })).toBeVisible();
  seen.expectClean();
});
