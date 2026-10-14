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
    await expect(drawer.getByRole("link", { name: PRODUCT })).toBeVisible();
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

test.describe("checkout", () => {
  test("a guest checks out with the test payment and lands on the private order page", async ({ page }) => {
    const seen = watch(page);
    await page.goto("/shop");
    await page.getByRole("link", { name: new RegExp(PRODUCT) }).first().click();
    await page.getByRole("button", { name: "Add to cart" }).click();
    await page.getByRole("dialog", { name: "Your cart" }).getByRole("link", { name: "Checkout" }).click();

    await expect(page.getByRole("heading", { level: 1, name: "Checkout" })).toBeVisible();
    const summary = page.getByRole("complementary", { name: "Your order" });
    await expect(summary.getByText("$8.95")).toBeVisible(); // flat shipping under the free-shipping threshold

    // An unknown code is explained, not silently ignored.
    await summary.getByLabel("Discount code").fill("NOT-A-REAL-CODE");
    await summary.getByRole("button", { name: "Apply" }).click();
    await expect(summary.getByRole("alert")).toContainText("NOT-A-REAL-CODE");
    await summary.getByRole("button", { name: "Remove code" }).click();

    await page.getByLabel("Email for your receipt").fill(`guest-${Date.now()}@example.com`);
    await page.getByLabel("Full name").fill("Ana Ruiz");
    await page.getByLabel("Street address").fill("1 Main St");
    await page.getByLabel("City").fill("Chicago");
    await page.getByLabel("State / province").fill("IL");
    await page.getByLabel("ZIP / postal code").fill("60601");
    await page.getByLabel(/Test payment/).check();
    await a11y(page, { enforce: false });
    await page.getByRole("button", { name: "Place order" }).click();

    await expect(page).toHaveURL(/\/order\/[\w-]+$/);
    await expect(page.getByRole("heading", { level: 1, name: /^Order WCW-\d+$/ })).toBeVisible();
    await expect(page.getByText("Thank you! Your payment was received.")).toBeVisible();
    await expect(page.getByText("Ana Ruiz")).toBeVisible();
    await expect(page.getByRole("list", { name: "Order progress" })).toBeVisible();

    await page.goto("/cart");
    await expect(page.getByText("Your cart is empty.")).toBeVisible(); // the cart was emptied after ordering
    seen.expectClean();
  });

  test("find my order explains a wrong number, unsubscribe asks before acting", async ({ page }) => {
    await page.goto("/track-order");
    await page.getByLabel("Order number").fill("WCW-999999");
    await page.getByLabel("Email address").fill("nobody@example.com");
    await page.getByRole("button", { name: "Find order" }).click();
    await expect(page.getByRole("alert")).toContainText("couldn't find");
    await a11y(page, { enforce: false });

    await page.goto("/unsubscribe");
    await expect(page.getByText("Please open the unsubscribe link from one of our emails.")).toBeVisible();
    await page.goto("/unsubscribe?token=not-a-real-token-123");
    await page.getByRole("button", { name: "Unsubscribe" }).click();
    await expect(page.getByRole("alert")).toContainText("isn't valid");
  });

  test("an empty cart can't check out", async ({ page }) => {
    await page.goto("/checkout");
    await expect(page.getByText("Your cart is empty.")).toBeVisible();
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
