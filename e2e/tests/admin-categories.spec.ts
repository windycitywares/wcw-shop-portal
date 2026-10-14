import { expect, test } from "@playwright/test";
import { adminApi, adminReady, adminState, unique, watch } from "./support";

test.use({ storageState: adminState });

/** If a test fails half-way, don't leave its categories behind for the next run. */
test.afterEach(async () => {
  const api = await adminApi();
  try {
    type Node = { id: number; name: string; children: Node[] };
    const tree = (await (await api.get("categories/tree")).json()) as Node[];
    const leftovers: Node[] = [];
    const walk = (nodes: Node[]) => nodes.forEach((n) => (walk(n.children), n.name.startsWith("E2E ") && leftovers.push(n)));
    walk(tree); // children are pushed before their parents
    for (const n of leftovers) await api.delete(`categories/${n.id}`);
  } finally {
    await api.dispose();
  }
});

test("add, edit, reorder and delete a category", async ({ page }) => {
  const seen = watch(page);
  const name = `E2E Category ${unique("c")}`;
  await page.goto("/admin/categories");
  await adminReady(page);

  // Add
  const form = page.locator("form").filter({ has: page.getByRole("heading", { name: "Add a category" }) });
  await form.getByLabel("Name", { exact: true }).fill(name);
  await form.getByRole("button", { name: "Add category" }).click();
  await expect(page.getByText("Category added")).toBeVisible();
  const tree = page.getByRole("region", { name: "Category tree" });
  const names = (text: string) => tree.getByTestId("category-name").filter({ hasText: text });
  await expect(names(name)).toBeVisible();

  // Edit
  await tree.getByRole("button", { name: `Edit ${name}` }).click();
  const edit = page.locator("form").filter({ has: page.getByRole("heading", { name: `Edit “${name}”` }) });
  await edit.getByLabel("Description").fill("Added by the browser tests");
  await edit.getByLabel("Visible in the shop").uncheck();
  await edit.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Saved", { exact: true })).toBeVisible();
  // `has` must be relative to the list item, so build it from the page rather than from `tree`.
  await expect(tree.getByRole("listitem").filter({ has: page.getByTestId("category-name").filter({ hasText: name }) }).getByText("Hidden")).toBeVisible();

  // Move up (it was added last among the top-level categories)
  const order = async () => (await tree.getByRole("listitem").allInnerTexts()).map((t) => t.split("\n")[0]);
  const before = await order();
  await tree.getByRole("button", { name: `Move ${name} up` }).click();
  await expect.poll(order).not.toEqual(before);

  // Delete
  await tree.getByRole("button", { name: `Edit ${name}` }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete category" }).click();
  await expect(page.getByText("Category deleted")).toBeVisible();
  await expect(names(name)).toHaveCount(0);

  seen.expectClean();
});

test("a category that still has a sub-category cannot be deleted", async ({ page }) => {
  const seen = watch(page, [{ status: 409 }]);
  const parent = `E2E Parent ${unique("p")}`;
  const child = `E2E Child ${unique("k")}`;
  await page.goto("/admin/categories");
  await adminReady(page);
  const form = () => page.locator("form").filter({ has: page.getByRole("heading", { name: "Add a category" }) });

  await form().getByLabel("Name", { exact: true }).fill(parent);
  await form().getByRole("button", { name: "Add category" }).click();
  await expect(page.getByText("Category added")).toBeVisible();

  await form().getByLabel("Name", { exact: true }).fill(child);
  await form().getByLabel("Parent").selectOption({ label: parent });
  await form().getByRole("button", { name: "Add category" }).click();
  const tree = page.getByRole("region", { name: "Category tree" });
  const names = (text: string) => tree.getByTestId("category-name").filter({ hasText: text });
  await expect(names(child)).toBeVisible();

  await tree.getByRole("button", { name: `Edit ${parent}` }).click();
  await page.getByRole("button", { name: "Delete", exact: true }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete category" }).click();
  await expect(page.locator("#admin-main").getByRole("alert")).toContainText("sub-categories");

  // Clean up: child first, then parent
  for (const name of [child, parent]) {
    await tree.getByRole("button", { name: `Edit ${name}` }).click();
    await page.getByRole("button", { name: "Delete", exact: true }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Delete category" }).click();
    await expect(names(name)).toHaveCount(0);
  }
  seen.expectClean();
});
