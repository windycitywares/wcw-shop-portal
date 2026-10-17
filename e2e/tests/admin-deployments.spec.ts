import { expect, test } from "@playwright/test";
import { adminReady, adminState, watch } from "./support";

test.use({ storageState: adminState });

test("deploy now can be queued and cancelled, and pausing asks first", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/admin/deployments");
  await adminReady(page);
  await expect(page.getByRole("heading", { name: "What's live" })).toBeVisible();
  await expect(page.getByLabel("Deploy log")).toBeVisible();

  // Queue a deploy, then take it back (nothing runs in CI: there is no cron job).
  await page.getByRole("button", { name: "Deploy now" }).click();
  await expect(page.getByText("Deploy queued", { exact: true })).toBeVisible();
  await expect(page.getByText("Queued", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Cancel deploy" }).click();
  await expect(page.getByText("Deploy cancelled", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Deploy now" })).toBeVisible();

  // Pausing asks first; then switch back to automatic every 10 minutes.
  await page.getByRole("radio", { name: /Paused/ }).check();
  await page.getByRole("button", { name: "Save update settings" }).click();
  const confirm = page.getByRole("dialog", { name: "Pause updates?" });
  await confirm.getByRole("button", { name: "Pause updates" }).click();
  await expect(page.getByText("Update settings saved", { exact: true })).toBeVisible();
  await expect(page.getByText("Paused: nothing installs on its own")).toBeVisible();

  await page.getByRole("radio", { name: /Automatic/ }).check();
  await page.getByLabel("Check every (minutes)").selectOption("10");
  await page.getByRole("button", { name: "Save update settings" }).click();
  await expect(page.getByText("Automatic, every 10 min")).toBeVisible();
  seen.expectClean();
});
