import { expect, test } from "@playwright/test";
import { adminReady, adminState, watch } from "./support";

test.use({ storageState: adminState });

test("a setting is saved, recorded in the audit log, and put back", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/admin/settings?tab=reviews");
  await adminReady(page);
  const days = page.getByLabel("Ask after (days)");
  const before = await days.inputValue();
  await days.fill(String(Number(before) + 1));
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Settings saved")).toBeVisible();

  await page.goto("/admin/audit");
  await adminReady(page);
  await expect(page.getByText("Changed reviews settings").first()).toBeVisible();

  await page.goto("/admin/settings?tab=reviews");
  await adminReady(page);
  await page.getByLabel("Ask after (days)").fill(before);
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Settings saved")).toBeVisible();
  seen.expectClean();
});

test("the review queue opens on the reviews waiting for approval", async ({ page }) => {
  await page.goto("/admin/reviews");
  await adminReady(page);
  await expect(page.getByRole("tab", { name: /To approve/ })).toHaveAttribute("aria-selected", "true");
});
