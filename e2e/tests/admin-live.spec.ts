import { expect, request, test } from "@playwright/test";
import { API, adminApi, adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("a new contact message pops up in the admin without a reload, and the bell says it is live", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/admin");
  await adminReady(page);

  // The bell's footer says how updates arrive: the stream from the storefront server.
  const bell = page.locator("summary", { hasText: "Notifications" }).first();
  await bell.click();
  await expect(page.getByTestId("live-status")).toHaveAttribute("data-mode", "stream", { timeout: 15_000 });
  await expect(page.getByTestId("live-status")).toHaveText("Live updates on");
  await page.keyboard.press("Escape");

  const api = await adminApi();
  const subject = unique("Live question");
  const sent = await api.post("contact", {
    data: { name: "Ari Live", email: `${unique("ari")}@example.com`, subject, message: "Do you ship to Canada?", locale: "en" },
  });
  expect(sent.status()).toBe(202);
  await api.dispose();

  // No reload: the toast arrives through the open stream.
  const toast = page.getByRole("status").filter({ hasText: `Message: ${subject}` });
  await expect(toast).toBeVisible({ timeout: 15_000 });
  await expect(toast).toContainText("From Ari Live");
  await expect(toast.getByRole("link", { name: "View" })).toHaveAttribute("href", /\/admin\/messages\?id=\d+/);
  seen.expectClean();
});

test("a new order offers a refresh on the orders list and pops up, without reloading by itself", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/admin/orders");
  await adminReady(page);
  const bell = page.locator("summary", { hasText: "Notifications" }).first();
  await bell.click();
  await expect(page.getByTestId("live-status")).toHaveAttribute("data-mode", "stream", { timeout: 15_000 });
  await page.keyboard.press("Escape");

  const api = await request.newContext({ baseURL: `${API}/` });
  const product = (await (await api.get("products?q=vase&page_size=1")).json()).items[0];
  const res = await api.post("checkout", {
    data: {
      items: [{ product_id: product.id, quantity: 1 }],
      email: `${unique("live-buyer")}@example.com`,
      shipping_address: { full_name: "Lou Live", line1: "1 Main St", city: "Chicago", region: "IL", postal_code: "60601", country: "US" },
      payment_method: "test",
    },
  });
  expect(res.status(), await res.text()).toBe(201);
  const order = (await res.json()).order;
  await api.dispose();

  await expect(page.getByRole("status").filter({ hasText: `New order #${order.number}` }).first()).toBeVisible({ timeout: 15_000 });
  const refresh = page.getByRole("button", { name: "Refresh" });
  await expect(refresh).toBeVisible();
  await refresh.click();
  await expect(refresh).toBeHidden();
  await expect(page.getByRole("link", { name: order.number })).toBeVisible();
  seen.expectClean();
});

test("notification settings decide what pops up: a newsletter sign-up after ticking it", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/admin/notifications/settings");
  await adminReady(page);
  await expect(page.getByTestId("live-mode")).toHaveText(/Live updates are on/, { timeout: 15_000 });
  await page.getByRole("button", { name: "Play test sound" }).click();

  const popup = page.getByLabel("Pop-up: Newsletter sign-ups and unsubscribes");
  await popup.check();
  await page.getByRole("button", { name: "Save settings" }).first().click();
  await expect(page.getByText("Notification settings saved", { exact: true })).toBeVisible();

  const api = await request.newContext({ baseURL: `${API}/` });
  const email = `${unique("live-news")}@example.com`;
  expect((await api.post("newsletter", { data: { email, locale: "en" } })).status()).toBeLessThan(300);
  await api.dispose();
  const toast = page.getByRole("status").filter({ hasText: "New newsletter subscriber" }).filter({ hasText: email });
  await expect(toast).toBeVisible({ timeout: 15_000 });

  // Put it back for the other tests (the admin login is shared).
  await popup.uncheck();
  await page.getByRole("button", { name: "Save settings" }).first().click();
  await expect(page.getByText("Notification settings saved", { exact: true }).first()).toBeVisible();
  seen.expectClean();
});
