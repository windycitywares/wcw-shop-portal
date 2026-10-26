import { expect, test } from "@playwright/test";
import { ADMIN_ROUTES } from "./admin-routes";
import { a11y, adminReady, adminState, expectNoHorizontalScroll, watch } from "./support";

test.use({ storageState: adminState });

// These tests wait for the network to go quiet; the admin's live-updates stream never does, so it is switched off here.
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("wcw-live", "off"));
});

for (const route of ADMIN_ROUTES) {
  test.describe(route.path, () => {
    test("loads without errors and passes the accessibility scan", async ({ page }) => {
      const seen = watch(page);
      await page.goto(route.path);
      await adminReady(page);
      await expect(page.locator("#admin-main h1").first()).toHaveText(route.heading);
      await page.waitForLoadState("networkidle");
      seen.expectClean();
      await a11y(page);
    });

    test("fits a phone screen", async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(route.path);
      await adminReady(page);
      await page.waitForLoadState("networkidle");
      await expectNoHorizontalScroll(page);
    });
  });
}

test("the dark theme passes the accessibility scan on the dashboard and the product list", async ({ page }) => {
  for (const path of ["/admin", "/admin/products"]) {
    await page.goto(`${path}?theme=midnight`);
    await adminReady(page);
    await page.waitForLoadState("networkidle");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "midnight");
    await a11y(page);
  }
});

test("the menu drawer works on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/admin");
  await adminReady(page);
  await page.getByRole("button", { name: "Open admin menu" }).click();
  const drawer = page.getByRole("dialog", { name: "Admin menu" });
  await expect(drawer).toBeVisible();
  await drawer.getByRole("link", { name: "Categories" }).click();
  await expect(page).toHaveURL(/\/admin\/categories/);
  await expect(drawer).toBeHidden();
  await expect(page.locator("#admin-main h1")).toHaveText("Categories");
});

test("the sidebar marks the current page", async ({ page }) => {
  await page.goto("/admin/products");
  await adminReady(page);
  await expect(page.locator("aside").getByRole("link", { name: "Products" })).toHaveAttribute("aria-current", "page");
  await expect(page.locator("aside").getByRole("link", { name: "Categories" })).not.toHaveAttribute("aria-current", "page");
});

test("switching the theme in the admin sticks across pages", async ({ page }) => {
  await page.goto("/admin");
  await adminReady(page);
  await page.getByRole("button", { name: "Dark mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "midnight");
  await page.goto("/admin/categories");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "midnight");
});
