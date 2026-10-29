import { expect, test } from "@playwright/test";
import { adminApi, adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("a newsletter sign-up shows in Subscribers, view-only, with a link to the CRM", async ({ page }) => {
  const api = await adminApi();
  const email = `${unique("news")}@example.com`;
  const joined = await api.post("newsletter", { data: { email, locale: "en" } });
  expect(joined.status()).toBe(202);

  const seen = watch(page);
  await page.goto("/admin/subscribers");
  await adminReady(page);
  await expect(page.getByTestId("crm-notice")).toContainText("managed in the CRM");
  await page.getByLabel("Search subscribers").fill(email);
  await page.getByRole("button", { name: "Search" }).click();
  const row = page.getByRole("row").filter({ hasText: email });
  await expect(row).toHaveCount(1);
  await expect(row.getByText("Subscribed", { exact: true })).toBeVisible();
  await expect(row.getByRole("link", { name: /in the CRM/ })).toHaveAttribute("href", /\/customers\?q=/);
  await expect(page.getByRole("button", { name: "Add subscriber" })).toHaveCount(0);
  await expect(row.getByRole("button")).toHaveCount(0);
  seen.expectClean();

  // Tidy up the test address through the API.
  const found = await api.get("admin/subscribers", { params: { status: "all", q: email } });
  const id = (await found.json()).items[0]?.id;
  if (id) await api.delete(`admin/subscribers/${id}`);
  await api.dispose();
});
