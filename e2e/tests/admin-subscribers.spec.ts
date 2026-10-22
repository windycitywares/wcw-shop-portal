import { expect, test } from "@playwright/test";
import { adminApi, adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("a newsletter sign-up shows in Subscribers and can be taken off the list and deleted", async ({ page }) => {
  const api = await adminApi();
  const email = `${unique("news")}@example.com`;
  const joined = await api.post("newsletter", { data: { email, locale: "en" } });
  expect(joined.status()).toBe(202);
  await api.dispose();

  const seen = watch(page);
  await page.goto("/admin/subscribers");
  await adminReady(page);
  await page.getByLabel("Search subscribers").fill(email);
  await page.getByRole("button", { name: "Search" }).click();
  const row = page.getByRole("row").filter({ hasText: email });
  await expect(row).toHaveCount(1);
  await expect(row.getByText("Subscribed", { exact: true })).toBeVisible();

  // Pausing asks first, shows the status, and resuming brings them back.
  await row.getByRole("button", { name: `Pause ${email}` }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Pause subscriber" }).click();
  await expect(page.getByText("Subscriber paused", { exact: true })).toBeVisible();
  await expect(row.getByText("Paused", { exact: true })).toBeVisible();
  await row.getByRole("button", { name: `Resume ${email}` }).click();
  await expect(page.getByText("Subscriber resumed", { exact: true })).toBeVisible();
  await expect(row.getByText("Subscribed", { exact: true })).toBeVisible();

  // Taking someone off the list asks first.
  await row.getByRole("button", { name: `Take ${email} off the list` }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Take off the list" }).click();
  await expect(page.getByText("Taken off the list", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: /Unsubscribed/ }).click();
  await expect(page.getByRole("row").filter({ hasText: email }).getByText("Unsubscribed", { exact: true })).toBeVisible();

  // Deleting asks for the code shown in the dialog.
  await page.getByRole("button", { name: `Delete ${email}` }).click();
  const dialog = page.getByRole("dialog");
  const code = (await dialog.locator("label[for=confirm-code] strong").textContent()) ?? "";
  await dialog.getByLabel(/To confirm, type/).fill(code);
  await dialog.getByRole("button", { name: "Delete subscriber" }).click();
  await expect(page.getByText("Subscriber deleted", { exact: true })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: email })).toHaveCount(0);
  seen.expectClean();
});
