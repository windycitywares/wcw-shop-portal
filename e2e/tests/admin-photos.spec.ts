import { expect, test } from "@playwright/test";
import { adminApi, adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

// A valid 2x2 PNG without transparency (saved as JPEG: only transparent PNGs stay PNG).
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGM4UaEBRAwQCgAp7gWhjAnOiAAAAABJRU5ErkJggg==",
  "base64",
);

test("a photo is uploaded, named after the product, and removed", async ({ page }) => {
  const api = await adminApi();
  const sku = unique("E2E-PHOTO").toUpperCase();
  const created = await api.post("products", { data: { title: `Oak Keepsake ${sku}`, sku, base_price: 25, status: "draft" } });
  expect(created.ok(), await created.text()).toBeTruthy();
  const { id } = (await created.json()) as { id: number };
  try {
    const seen = watch(page);
    await page.goto(`/admin/products/${id}`);
    await adminReady(page);
    await page.getByLabel("Upload photos").setInputFiles({ name: "IMG_0042.png", mimeType: "image/png", buffer: PNG });
    await expect(page.getByText("Photo uploaded")).toBeVisible();
    const photos = page.getByRole("list", { name: /Photos, in the order shown/ });
    await expect(photos.getByRole("listitem")).toHaveCount(1);

    const saved = (await (await api.get(`products/by-id/${id}`)).json()) as { images: { url: string }[] };
    expect(saved.images[0].url).toMatch(new RegExp(`/products/[^/]+/oak-keepsake-${sku.toLowerCase()}-1\\.jpg$`));

    await photos.getByRole("button", { name: "Remove photo 1" }).click();
    await expect(page.getByText("Photo removed")).toBeVisible();
    await expect(photos).toHaveCount(0);
    seen.expectClean();
  } finally {
    await api.delete(`products/${id}`);
    await api.dispose();
  }
});
