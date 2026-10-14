import { expect, request, test } from "@playwright/test";
import { API, adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

/** Places a real order through the shop API (test payment, so it is paid at once). */
async function placeOrder(): Promise<{ id: number; number: string }> {
  const api = await request.newContext({ baseURL: `${API}/` });
  const found = await (await api.get("products?q=vase&page_size=1")).json();
  const product = found.items[0];
  const res = await api.post("checkout", {
    data: {
      items: [{ product_id: product.id, quantity: 2 }],
      email: `${unique("buyer")}@example.com`,
      shipping_address: { full_name: "Ana Ruiz", line1: "1 Main St", city: "Chicago", region: "IL", postal_code: "60601", country: "US" },
      payment_method: "test",
    },
  });
  expect(res.status(), await res.text()).toBe(201);
  const order = (await res.json()).order;
  await api.dispose();
  return { id: order.id, number: order.number };
}

test("an order can be found, shipped, delivered and partly refunded", async ({ page }) => {
  const seen = watch(page);
  const order = await placeOrder();

  await page.goto("/admin/orders");
  await adminReady(page);
  await page.getByLabel("Search orders").fill(order.number);
  await page.getByRole("button", { name: "Search" }).click();
  await page.getByRole("link", { name: order.number }).click();
  await expect(page.locator("#admin-main h1")).toHaveText(`Order ${order.number}`);

  await page.getByLabel("Add an internal note").fill("Call before delivery");
  await page.getByRole("button", { name: "Add note" }).click();
  await expect(page.getByText("Call before delivery")).toBeVisible();

  await page.getByRole("button", { name: "Ship order" }).click();
  const ship = page.getByRole("dialog", { name: "Ship order" });
  await ship.getByLabel("Tracking number").fill("9400 1000 0000 0000 0000 00");
  await ship.getByRole("button", { name: "Mark as shipped" }).click();
  await expect(page.getByText("Shipped").first()).toBeVisible();

  await page.getByRole("button", { name: "Mark delivered" }).click();
  await expect(page.getByText("Delivered").first()).toBeVisible();

  await page.getByRole("button", { name: "Refund" }).click();
  const refund = page.getByRole("dialog", { name: "Refund" });
  await refund.getByLabel("Amount").fill("5");
  await refund.getByRole("button", { name: /^Refund \$5\.00$/ }).click();
  await expect(page.getByText("Partly refunded")).toBeVisible();
  seen.expectClean();
});
