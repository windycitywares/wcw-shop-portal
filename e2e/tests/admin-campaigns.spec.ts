import { expect, test } from "@playwright/test";
import { adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("a campaign draft can be written, saved and offered for sending", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/admin/campaigns");
  await adminReady(page);
  const name = unique("Thank you");
  await page.getByRole("button", { name: "New campaign" }).click();
  const dialog = page.getByRole("dialog", { name: "New campaign" });
  await dialog.getByLabel("Name", { exact: true }).fill(name);
  await dialog.getByLabel("Subject", { exact: true }).fill("A small thank-you");
  await dialog.getByLabel("Message", { exact: true }).fill("Thank you for trusting us.\n\nHere is a code for your next order.");
  await dialog.getByLabel("Code for each recipient").selectOption("percent");
  await dialog.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible();

  // Sending asks first and says how many people it reaches; cancel here (sending happens once and for real).
  await page.getByRole("button", { name: `Send ${name}` }).click();
  const confirm = page.getByRole("dialog", { name: `Send "${name}"?` });
  await expect(confirm.getByText(/It goes to \d+ (person|people)/)).toBeVisible();
  await confirm.getByRole("button", { name: "Cancel" }).click();
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
