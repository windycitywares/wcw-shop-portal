import { expect, test } from "@playwright/test";
import { ADMIN_EMAIL, ADMIN_PASSWORD, adminApi, signedOut, unique, watch } from "./support";

test.use({ storageState: signedOut });

test.describe("signing in", () => {
  test("a wrong password is refused with a clear message", async ({ page }) => {
    const seen = watch(page, [{ status: 401 }]);
    await page.goto("/login");
    await page.getByLabel("Email", { exact: true }).fill(ADMIN_EMAIL);
    await page.getByLabel("Password", { exact: true }).fill("definitely-not-the-password");
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.locator("main").getByRole("alert")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
    seen.expectClean();
  });

  test("the admin signs in, lands on the dashboard and can sign out", async ({ page }) => {
    const seen = watch(page);
    await page.goto("/login");
    await page.getByLabel("Email", { exact: true }).fill(ADMIN_EMAIL);
    await page.getByLabel("Password", { exact: true }).fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/admin$/);
    await expect(page.locator("#admin-main h1")).toBeVisible();

    await page.locator("details > summary").filter({ hasText: "Account menu" }).click();
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/);
    seen.expectClean();
  });

  test("visiting /admin signed out sends you to sign in", async ({ page }) => {
    await page.goto("/admin/products");
    await expect(page).toHaveURL(/\/login/);
  });

  test("a customer account cannot use the admin", async ({ page }) => {
    const api = await adminApi();
    const email = `${unique("customer")}@example.com`;
    const password = "Customer-pass-123";
    const created = await api.post("users", { data: { email, password, full_name: "E2E Customer", role: "customer" } });
    expect(created.ok(), await created.text()).toBeTruthy();
    const { id } = (await created.json()) as { id: number };
    try {
      await page.goto("/login");
      await page.getByLabel("Email", { exact: true }).fill(email);
      await page.getByLabel("Password", { exact: true }).fill(password);
      await page.getByRole("button", { name: "Sign in" }).click();
      await expect(page).toHaveURL(/\/account/);
      await page.goto("/admin");
      await expect(page).not.toHaveURL(/\/admin$/);
    } finally {
      await api.patch(`users/${id}`, { data: { is_active: false } });
      await api.dispose();
    }
  });
});
