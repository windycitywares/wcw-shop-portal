import { test } from "@playwright/test";
import { ADMIN_ROUTES } from "./admin-routes";
import { adminReady, adminState, shot, signedOut } from "./support";

/**
 * Screenshots for design review. They are written to e2e/shots and the workflow publishes them to the
 * `e2e-shots` branch of the repository. These tests only fail if a page cannot be reached.
 */
test.describe("admin", () => {
  test.use({ storageState: adminState });

  for (const route of ADMIN_ROUTES) {
    test(`${route.name} (desktop)`, async ({ page }) => {
      await page.goto(route.path);
      await adminReady(page);
      await page.waitForLoadState("networkidle");
      await shot(page, `admin-${route.name}-desktop`);
    });
  }

  for (const name of ["dashboard", "products", "categories"]) {
    const route = ADMIN_ROUTES.find((r) => r.name === name)!;
    test(`${route.name} (phone)`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(route.path);
      await adminReady(page);
      await page.waitForLoadState("networkidle");
      await shot(page, `admin-${route.name}-phone`);
    });
    test(`${route.name} (midnight)`, async ({ page }) => {
      await page.goto(`${route.path}?theme=midnight`);
      await adminReady(page);
      await page.waitForLoadState("networkidle");
      await shot(page, `admin-${route.name}-midnight`);
    });
  }
});

test.describe("storefront", () => {
  test.use({ storageState: signedOut });

  for (const [name, path] of [
    ["home", "/"],
    ["shop", "/shop"],
    ["cart", "/cart"],
  ] as const) {
    test(`${name} (desktop)`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await shot(page, `shop-${name}-desktop`);
    });
    test(`${name} (phone)`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await shot(page, `shop-${name}-phone`);
    });
  }
});
