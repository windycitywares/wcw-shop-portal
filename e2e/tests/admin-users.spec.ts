import { expect, test } from "@playwright/test";
import { adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("add a team member, change their role and switch the account off", async ({ page }) => {
  const seen = watch(page);
  const email = `${unique("team")}@example.com`;
  await page.goto("/admin/users");
  await adminReady(page);

  await page.getByRole("button", { name: "Add team member" }).click();
  const dialog = page.getByRole("dialog", { name: "Add a team member" });
  await dialog.getByLabel("Name").fill("E2E Teammate");
  await dialog.getByLabel("Email").fill(email);
  await dialog.getByLabel("Temporary password").fill("Teammate-pass-123");
  await dialog.getByLabel("Role").selectOption("author");
  await dialog.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByText("Account created")).toBeVisible();
  await expect(dialog).toBeHidden();

  await page.getByRole("searchbox", { name: "Search people" }).fill(email);
  await page.getByRole("button", { name: "Search" }).click();
  const row = page.getByRole("row").filter({ hasText: email });
  await expect(row).toHaveCount(1);
  await expect(row.getByText("Active", { exact: true })).toBeVisible();

  // Changing a role asks first; cancelling keeps the old one.
  const role = row.getByLabel(`Role for ${email}`);
  await role.selectOption("publisher");
  const confirm = page.getByRole("dialog", { name: "Change role?" });
  await expect(confirm).toContainText("from author to publisher", { ignoreCase: true });
  await confirm.getByRole("button", { name: "Cancel" }).click();
  await expect(confirm).toBeHidden();
  await expect(role).toHaveValue("author");

  await role.selectOption("publisher");
  await confirm.getByRole("button", { name: "Make publisher" }).click();
  await expect(page.getByText("Role changed", { exact: true })).toBeVisible();
  await expect(confirm).toBeHidden();
  await expect(role).toHaveValue("publisher");
  // Saved on the server, not just in the page.
  await page.reload();
  await adminReady(page);
  await page.getByRole("searchbox", { name: "Search people" }).fill(email);
  await page.getByRole("button", { name: "Search" }).click();
  await expect(row.getByLabel(`Role for ${email}`)).toHaveValue("publisher");

  // Switching the account off asks too; the checkbox only flips once it is saved.
  await row.getByLabel(`Account active for ${email}`).click();
  const off = page.getByRole("dialog", { name: "Switch this account off?" });
  await off.getByRole("button", { name: "Switch off" }).click();
  await expect(row.getByText("Disabled")).toBeVisible();
  await expect(row.getByLabel(`Account active for ${email}`)).not.toBeChecked();
  seen.expectClean();
});

test("the same email cannot be added twice", async ({ page }) => {
  await page.goto("/admin/users");
  await adminReady(page);
  await page.getByRole("button", { name: "Add team member" }).click();
  const dialog = page.getByRole("dialog", { name: "Add a team member" });
  await dialog.getByLabel("Email").fill(process.env.ADMIN_EMAIL || "");
  await dialog.getByLabel("Temporary password").fill("Teammate-pass-123");
  await dialog.getByRole("button", { name: "Create account" }).click();
  await expect(dialog.getByRole("alert")).toBeVisible();
  await expect(dialog).toBeVisible();
});

test("you cannot change your own role or switch yourself off", async ({ page }) => {
  await page.goto("/admin/users");
  await adminReady(page);
  const email = process.env.ADMIN_EMAIL || "";
  const row = page.getByRole("row").filter({ hasText: email });
  await expect(row.getByLabel(`Role for ${email}`)).toBeDisabled();
  await expect(row.getByLabel(`Account active for ${email}`)).toBeDisabled();
});
