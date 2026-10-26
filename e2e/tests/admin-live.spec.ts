import { expect, test } from "@playwright/test";
import { adminApi, adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("a new contact message pops up in the admin without a reload, and the bell says it is live", async ({ page }) => {
  const seen = watch(page);
  await page.goto("/admin");
  await adminReady(page);

  // The bell's footer says how updates arrive: the stream from the storefront server.
  const bell = page.getByRole("button", { name: /^Notifications/ });
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
