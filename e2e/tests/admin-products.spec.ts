import { expect, test } from "@playwright/test";
import { API, adminApi, adminReady, adminState, unique, watch, confirmDelete } from "./support";

test.use({ storageState: adminState });

test.describe("product lifecycle", () => {
  test("create, publish, see it in the shop, edit, unpublish and delete", async ({ page, request }) => {
    const seen = watch(page);
    const sku = unique("E2E").toUpperCase();
    const title = `E2E Test Urn ${sku}`;

    // Create as a published product
    await page.goto("/admin/products/new");
    await adminReady(page);
    await page.getByLabel("Title", { exact: true }).fill(title);
    await page.getByLabel("Description", { exact: true }).fill("A test urn created by the automated browser tests.");
    await page.getByLabel("SKU").fill(sku);
    await page.getByLabel("Price (USD)").fill("49.50");
    await page.getByLabel("Compare-at price").fill("60");
    await page.getByLabel("Quantity").fill("5");
    await page.getByLabel("Visibility").selectOption("published");
    await page.getByRole("button", { name: "Create product" }).click();

    await expect(page).toHaveURL(/\/admin\/products\/\d+$/);
    await expect(page.locator("#admin-main h1")).toHaveText(title);
    await expect(page.getByText("Product created")).toBeVisible();
    const slugHref = await page.getByRole("link", { name: "View in shop" }).getAttribute("href");
    expect(slugHref).toMatch(/^\/product\//);

    // It is on sale: 15%+ off is shown on the edit page and the shop page
    await expect(page.getByText(/Shown as a sale: 18% off/)).toBeVisible();
    await request.get(`${slugHref}`).then(async (res) => {
      expect(res.status()).toBe(200);
      expect(await res.text()).toContain(title);
    });
    await page.goto(slugHref!);
    await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expect(page.getByText("$49.50").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Add to cart" })).toBeEnabled();

    // Edit the price
    await page.goBack();
    await page.getByLabel("Price (USD)").fill("55");
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByText("Saved", { exact: true })).toBeVisible();

    // Find it in the list and unpublish
    await page.goto("/admin/products");
    await page.getByRole("searchbox", { name: "Search products" }).fill(sku);
    await page.getByRole("button", { name: "Search" }).click();
    const row = page.getByRole("row").filter({ hasText: sku });
    await expect(row).toHaveCount(1);
    await expect(row.getByText("Published", { exact: true }).filter({ visible: true })).toBeVisible();
    await expect(row.getByText("$55.00")).toBeVisible();
    await row.getByRole("button", { name: "Unpublish" }).click();
    await expect(page.getByText("Unpublished", { exact: true })).toBeVisible();

    // The public API stops serving it straight away. (Storefront pages are cached for a few minutes.)
    const slug = slugHref!.split("/").pop();
    const hidden = await request.get(`${API}/products/${slug}`);
    expect(hidden.status()).toBe(404);

    // Delete it
    await row.getByRole("link", { name: title }).click();
    await expect(page.locator("#admin-main h1")).toHaveText(title);
    await page.getByRole("button", { name: "Delete product", exact: true }).click();
    await confirmDelete(page, "Delete product");
    await expect(page).toHaveURL(/\/admin\/products$/);
    await page.getByRole("searchbox", { name: "Search products" }).fill(sku);
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByText("No products match.")).toBeVisible();

    seen.expectClean();
  });

  test("the status tabs filter the list", async ({ page }) => {
    const api = await adminApi();
    const sku = unique("E2E-DRAFT").toUpperCase();
    const created = await api.post("products", { data: { title: `E2E Draft ${sku}`, sku, base_price: 10, status: "draft" } });
    expect(created.ok(), await created.text()).toBeTruthy();
    const { id } = (await created.json()) as { id: number };
    try {
      await page.goto("/admin/products");
      await adminReady(page);
      await page.getByRole("tab", { name: "Draft" }).click();
      await page.getByRole("searchbox", { name: "Search products" }).fill(sku);
      await page.getByRole("button", { name: "Search" }).click();
      const row = page.getByRole("row").filter({ hasText: sku });
      await expect(row).toHaveCount(1);
      await expect(row.getByText("Draft", { exact: true }).filter({ visible: true })).toBeVisible();

      await page.getByRole("tab", { name: "Published" }).click();
      await expect(page.getByText("No products match.")).toBeVisible();

      // Submit for review, then publish, from the list
      await page.getByRole("tab", { name: "Draft" }).click();
      await row.getByRole("button", { name: "Submit for review" }).click();
      await expect(page.getByText("Sent for review")).toBeVisible();
      await page.getByRole("tab", { name: "In review" }).click();
      await row.getByRole("button", { name: "Publish" }).click();
      await expect(page.getByRole("status").filter({ hasText: "Published" })).toBeVisible();
    } finally {
      await api.delete(`products/${id}`);
      await api.dispose();
    }
  });

  test("a sale price needs a higher compare-at price to show as a sale", async ({ page }) => {
    await page.goto("/admin/products/new");
    await adminReady(page);
    await page.getByLabel("Price (USD)").fill("40");
    await page.getByLabel("Compare-at price").fill("30");
    await expect(page.getByText("The original price. Fill in to show a sale.")).toBeVisible();
    await page.getByLabel("Compare-at price").fill("50");
    await expect(page.getByText("Shown as a sale: 20% off.")).toBeVisible();
  });
});
