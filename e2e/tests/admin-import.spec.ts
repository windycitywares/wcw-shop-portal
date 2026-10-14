import { expect, test } from "@playwright/test";
import { adminApi, adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

test("preview and import an Etsy CSV, then update it by importing again", async ({ page }) => {
  const seen = watch(page);
  const tag = unique("e2eimp").toUpperCase();
  const csv = [
    "TITLE,DESCRIPTION,PRICE,CURRENCY_CODE,QUANTITY,TAGS,SKU",
    `"E2E Import Urn One ${tag}","First imported urn",31.00,USD,4,"e2e,urn",${tag}-1`,
    `"E2E Import Urn Two ${tag}","Second imported urn",42.50,USD,2,"e2e",${tag}-2`,
  ].join("\n");
  const file = { name: "EtsyListingsDownload.csv", mimeType: "text/csv", buffer: Buffer.from(csv) };

  await page.goto("/admin/import");
  await adminReady(page);
  await expect(page.getByRole("button", { name: "Preview" })).toBeDisabled();
  await page.getByLabel("File").setInputFiles(file);

  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText("Nothing has been saved yet.")).toBeVisible();
  const preview = page.getByRole("table", { name: "Import preview" });
  await expect(preview.getByRole("row")).toHaveCount(3); // header + 2 products
  await expect(preview.getByText(`E2E Import Urn One ${tag}`)).toBeVisible();

  await page.getByRole("button", { name: "Import", exact: true }).click();
  await expect(page.getByText(/Import finished: 2 created, 0 updated/)).toBeVisible();

  // Same file again: matched by SKU, so nothing is duplicated
  await page.getByLabel("File").setInputFiles(file);
  await page.getByRole("button", { name: "Import", exact: true }).click();
  await expect(page.getByText(/Import finished: 0 created, 2 updated/)).toBeVisible();

  // Imported as drafts
  await page.getByRole("link", { name: "Review imported products" }).click();
  await page.getByRole("searchbox", { name: "Search products" }).fill(tag);
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByRole("row").filter({ hasText: tag })).toHaveCount(2);

  const api = await adminApi();
  try {
    const found = await api.get(`products?q=${tag}&page_size=10&status=draft`);
    const { items } = (await found.json()) as { items: { id: number }[] };
    expect(items).toHaveLength(2);
    for (const p of items) await api.delete(`products/${p.id}`);
  } finally {
    await api.dispose();
  }
  seen.expectClean();
});

test("a file that is not an Etsy export is explained, not accepted", async ({ page }) => {
  const seen = watch(page, [{ status: 400 }, { status: 422 }]);
  await page.goto("/admin/import");
  await adminReady(page);
  await page.getByLabel("File").setInputFiles({ name: "wrong.csv", mimeType: "text/csv", buffer: Buffer.from("name,cost\nx,1\n") });
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.locator("#admin-main").getByRole("alert")).toContainText(/Etsy/);
  void seen;
});

test("the catalog can be exported to Excel", async ({ page }) => {
  await page.goto("/admin/import");
  await adminReady(page);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: /Export catalog/ }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("wcw-catalog.xlsx");
});
