import { expect, test, type APIRequestContext } from "@playwright/test";
import { adminApi, adminState, signedOut, unique, watch } from "./support";

/** An out-of-stock product with a size choice, made for the test and deleted after it. */
async function soldOutProduct(api: APIRequestContext) {
  const sku = unique("E2E-SOLD").toUpperCase();
  const r = await api.post("products", {
    data: {
      title: `E2E Sold Out ${sku}`, sku, base_price: 30, status: "published", stock_status: "out_of_stock", stock_quantity: 0,
      attributes: { Size: ["Small", "Large"] },
    },
  });
  expect(r.ok(), await r.text()).toBeTruthy();
  return (await r.json()) as { id: number; slug: string; title: string };
}

test.describe("signed out", () => {
  test.use({ storageState: signedOut });

  test("an out-of-stock product invites the shopper to sign in to be notified", async ({ page }) => {
    const api = await adminApi();
    const p = await soldOutProduct(api);
    try {
      await page.goto(`/product/${p.slug}`);
      await expect(page.getByRole("button", { name: "Out of stock" })).toBeDisabled();
      await page.getByRole("button", { name: "Notify me when it's available" }).click();
      const dialog = page.getByRole("dialog");
      await expect(dialog.getByRole("heading", { name: "Sign in to get notified" })).toBeVisible();
      await expect(dialog.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", new RegExp(`/login\\?next=.*${p.slug}`));
      await expect(dialog.getByRole("link", { name: "Create an account" })).toHaveAttribute("href", /mode=register/);
    } finally {
      await api.delete(`products/${p.id}`);
      await api.dispose();
    }
  });
});

test.describe("signed in", () => {
  test.use({ storageState: adminState });

  test("a customer asks for a size and sees the request in their account", async ({ page }) => {
    const api = await adminApi();
    const p = await soldOutProduct(api);
    try {
      const seen = watch(page);
      await page.goto(`/product/${p.slug}`);
      await page.getByRole("button", { name: "Notify me when it's available" }).click();
      const dialog = page.getByRole("dialog");
      await dialog.getByLabel("Size").selectOption("Large");
      await expect(dialog.getByText(/out of stock right now/)).toBeVisible();
      await dialog.getByLabel("Anything we should know? (optional)").fill("Needed by November");
      await dialog.getByRole("button", { name: "Notify me" }).click();
      await expect(dialog.getByRole("status")).toContainText("as soon as");
      await expect(dialog.getByRole("link", { name: "See my requests" })).toHaveAttribute("href", "/account#my-stock-requests");
      const fromApi = await api.get("account/stock-requests");
      const body = await fromApi.text();
      expect(fromApi.status(), body).toBe(200);
      expect(body, "the API lists the new request").toContain(p.title);
      await page.goto("/account");
      const mine = page.locator("#my-stock-requests");
      await expect(mine.getByRole("heading", { name: "My stock requests" })).toBeVisible();
      await expect(mine.getByText(p.title)).toBeVisible();
      await expect(mine.getByText("Size: Large")).toBeVisible();
      await mine.getByRole("button", { name: new RegExp(`Cancel request ${p.title}`) }).click();
      await expect(page.getByText("Request cancelled.")).toBeVisible();
      seen.expectClean();
    } finally {
      await api.delete(`products/${p.id}`);
      await api.dispose();
    }
  });
});
