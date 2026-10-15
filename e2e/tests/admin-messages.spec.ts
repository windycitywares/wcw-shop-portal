import { expect, test } from "@playwright/test";
import { adminApi, adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("a contact message is read, answered by email and leaves the inbox", async ({ page }) => {
  const api = await adminApi();
  const subject = unique("Engraving question");
  const sent = await api.post("contact", {
    data: { name: "Mia Park", email: `${unique("mia")}@example.com`, subject, message: "Can the urn be engraved with two names?", locale: "en" },
  });
  expect(sent.status()).toBe(202);
  await api.dispose();

  const seen = watch(page);
  await page.goto("/admin/messages");
  await adminReady(page);
  await page.getByLabel("Search messages").fill(subject);
  await page.getByRole("button", { name: "Search" }).click();
  await page.getByRole("button", { name: new RegExp(subject) }).click();

  const message = page.getByRole("region", { name: `Message: ${subject}` });
  await expect(message.getByText("Can the urn be engraved with two names?")).toBeVisible();
  await message.getByLabel("Reply to Mia Park").fill("Yes, two names fit nicely.");
  await message.getByRole("button", { name: "Send reply" }).click();
  await expect(page.getByText(/^Reply (sent|saved)/)).toBeVisible();
  await expect(message.getByRole("list", { name: "Replies" })).toContainText("Yes, two names fit nicely.");
  seen.expectClean();
});
