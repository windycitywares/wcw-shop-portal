import { expect, test } from "@playwright/test";
import { adminApi, adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("the bell counts new activity and opens it where it's handled", async ({ page }) => {
  const api = await adminApi();
  await api.post("admin/notifications/seen");
  const subject = unique("Bell question");
  await api.post("contact", { data: { name: "Ida Bell", email: `${unique("ida")}@example.com`, subject, message: "Do you ship to Canada?", locale: "en" } });
  await api.dispose();

  const seen = watch(page);
  await page.goto("/admin");
  await adminReady(page);
  const bell = page.locator("summary", { hasText: /Notifications, \d+ new/ });
  await expect(bell).toBeVisible();
  await bell.click();
  const item = page.getByRole("link", { name: new RegExp(`Message: ${subject}`) });
  await expect(item).toBeVisible();
  await item.click();
  await expect(page).toHaveURL(/\/admin\/messages\?id=\d+/);
  await expect(page.getByRole("region", { name: `Message: ${subject}` })).toBeVisible();
  await expect(page.locator("summary", { hasText: "Notifications" }).first()).not.toContainText("new");
  seen.expectClean();
});
