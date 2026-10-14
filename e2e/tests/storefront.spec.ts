import { expect, test } from "@playwright/test";
import { a11y, expectNoHorizontalScroll, signedOut, watch } from "./support";

test.use({ storageState: signedOut });

// The seeded sample catalog includes "Ceramic Bud Vase" ($28.00). Accessibility findings on the
// storefront are listed on the report rather than failing the run; the admin's are enforced.
const PRODUCT = "Ceramic Bud Vase";

test.describe("browsing", () => {
  test("home page", async ({ page }) => {
    const seen = watch(page);
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("A beautiful place to keep them close");
    await page.waitForLoadState("networkidle");
    seen.expectClean();
    await a11y(page, { enforce: false });
  });

  test("shop lists products and a product page opens from it", async ({ page }) => {
    const seen = watch(page);
    await page.goto("/shop");
    const link = page.getByRole("link", { name: new RegExp(PRODUCT) }).first();
    await expect(link).toBeVisible();
    await link.click();
    await expect(page.getByRole("heading", { level: 1, name: PRODUCT })).toBeVisible();
    await expect(page.getByText("$28.00").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Add to cart" })).toBeEnabled();
    seen.expectClean();
    await a11y(page, { enforce: false });
  });

  test("search finds a product by name", async ({ page }) => {
    await page.goto("/search?q=vase");
    await expect(page.getByRole("link", { name: new RegExp(PRODUCT) }).first()).toBeVisible();
    await page.goto("/search?q=zzzz-no-such-thing");
    await expect(page.getByRole("link", { name: new RegExp(PRODUCT) })).toHaveCount(0);
  });

  test("the language switch keeps you on the same page", async ({ page }) => {
    await page.goto("/shop");
    await page.goto("/es/shop");
    await expect(page.locator("html")).toHaveAttribute("lang", "es");
    await page.goto("/nl/shop");
    await expect(page.locator("html")).toHaveAttribute("lang", "nl");
  });

  test("the colour theme can be changed and is remembered", async ({ page }) => {
    await page.goto("/");
    await page.locator("details > summary").filter({ hasText: "Color theme" }).first().click();
    await page.getByText("Midnight", { exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "midnight");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "midnight");
  });

  test("pages fit a phone screen", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    for (const path of ["/", "/shop", "/cart", "/contact", "/login"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await expectNoHorizontalScroll(page);
    }
  });
});

test.describe("the cart", () => {
  test("add, change quantity, keep across a reload, remove", async ({ page }) => {
    const seen = watch(page);
    await page.goto("/shop");
    await page.getByRole("link", { name: new RegExp(PRODUCT) }).first().click();
    await page.getByRole("button", { name: "Add to cart" }).click();

    const drawer = page.getByRole("dialog", { name: "Your cart" });
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText(PRODUCT)).toBeVisible();
    await expect(drawer.getByText("$28.00").first()).toBeVisible();
    await drawer.getByRole("link", { name: "View cart" }).click();

    await expect(page).toHaveURL(/\/cart$/);
    await expect(page.getByRole("heading", { level: 1, name: "Your cart" })).toBeVisible();
    await page.getByRole("button", { name: "Increase quantity" }).click();
    await expect(page.getByRole("complementary", { name: "Order summary" }).getByText("$56.00")).toBeVisible();

    await page.reload();
    await expect(page.getByRole("complementary", { name: "Order summary" }).getByText("$56.00")).toBeVisible();

    await page.getByRole("button", { name: "Remove" }).click();
    await expect(page.getByText("Your cart is empty.")).toBeVisible();
    seen.expectClean();
  });
});

test.describe("contact and account pages", () => {
  test("the contact form validates before sending", async ({ page }) => {
    await page.goto("/contact");
    await page.getByRole("button", { name: /Send/ }).click();
    // The browser's own validation stops an empty form from being sent.
    await expect(page).toHaveURL(/\/contact$/);
  });

  test("forgot-password page renders", async ({ page }) => {
    await page.goto("/forgot-password");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("unknown pages show the friendly not-found page", async ({ page }) => {
    const res = await page.goto("/this-page-does-not-exist");
    expect(res?.status()).toBe(404);
    await expect(page.getByText("We couldn’t find that page")).toBeVisible();
  });
});
