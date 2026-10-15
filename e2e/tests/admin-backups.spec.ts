import { expect, test } from "@playwright/test";
import { adminApi, adminReady, adminState, watch } from "./support";

test.use({ storageState: adminState });

test("backup settings save the repository typed in (a pasted GitHub address works too)", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/admin/backups");
  await adminReady(page);
  await page.getByLabel("Private GitHub repository").fill("https://github.com/windycitywares/wcw-backups-e2e.git");
  await page.getByLabel("Backups to keep").fill("6");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByText("Backup settings saved")).toBeVisible();
  await expect(page.getByLabel("Private GitHub repository")).toHaveValue("windycitywares/wcw-backups-e2e");

  const api = await adminApi();
  try {
    const saved = (await (await api.get("admin/backups")).json()) as { repo: string; keep: number; enabled: boolean };
    expect([saved.repo, saved.keep, saved.enabled]).toEqual(["windycitywares/wcw-backups-e2e", 6, false]);
    await api.put("admin/backups", { data: { enabled: false, hour: 3, keep: 5, repo: null, branch: "main" } });
  } finally {
    await api.dispose();
  }
  seen.expectClean();
});
