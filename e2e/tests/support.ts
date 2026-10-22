import AxeBuilder from "@axe-core/playwright";
import { expect, request, test, type APIRequestContext, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

export const API = (process.env.E2E_API_URL || "http://localhost:8000/api/v1").replace(/\/$/, "");
export const ADMIN_EMAIL = process.env.ADMIN_EMAIL || "";
export const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || "";

const root = path.join(__dirname, "..");
export const adminState = path.join(root, ".auth", "admin.json");
export const BASE_URL = (process.env.E2E_BASE_URL || "http://localhost:3000").replace(/\/$/, "");
/** Signed out, with the analytics banner already answered ("No thanks") so it never covers what a test clicks. */
export const signedOut = {
  cookies: [],
  origins: [{ origin: BASE_URL, localStorage: [{ name: "wcw-consent", value: "declined" }] }],
};
/** Signed out and the banner not answered yet (a first visit). */
export const firstVisit = { cookies: [], origins: [] };
const shotsDir = path.join(root, "shots");

/** A name that is unique per run, so repeated runs against the same database never collide. */
export const unique = (prefix: string) => `${prefix}-${Date.now().toString(36)}${Math.floor(Math.random() * 1296).toString(36)}`;

/** API client acting as the seeded admin. Dispose it when done (`await api.dispose()`). */
export async function adminApi(): Promise<APIRequestContext> {
  const token = fs.readFileSync(path.join(root, ".auth", "token.txt"), "utf8").trim();
  return request.newContext({ baseURL: `${API}/`, extraHTTPHeaders: { Authorization: `Bearer ${token}` } });
}

/** Paths are relative to the API root ("products", not "/products"), so they resolve under /api/v1/. */
export const apiPath = (p: string) => p.replace(/^\//, "");

/** Console noise that isn't a defect in our code. */
const IGNORED_CONSOLE = [
  /challenges\.cloudflare\.com/i,
  /Download the React DevTools/i,
  /favicon/i,
];

/**
 * Collects JavaScript errors, error-level console output and failed API calls while a page runs.
 * Call `expectClean()` at the end of a test; pass `allow` for API statuses a test provokes on purpose.
 */
export function watch(page: Page, allow: { status: number; url?: RegExp }[] = []) {
  const problems: string[] = [];
  page.on("pageerror", (e) => problems.push(`page error: ${e.message}`));
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const text = m.text();
    if (IGNORED_CONSOLE.some((r) => r.test(text))) return;
    // "Failed to load resource" lines are reported with the URL by the response handler below.
    if (/Failed to load resource/i.test(text)) return;
    problems.push(`console error: ${text}`);
  });
  page.on("response", (r) => {
    const url = r.url();
    if (r.status() < 400) return;
    if (!url.startsWith(API) && r.request().resourceType() !== "document") return;
    if (allow.some((a) => a.status === r.status() && (!a.url || a.url.test(url)))) return;
    problems.push(`${r.status()} ${r.request().method()} ${url}`);
  });
  return {
    problems,
    expectClean() {
      expect(problems, `Unexpected problems:\n${problems.join("\n")}`).toEqual([]);
    },
  };
}

type Impact = "minor" | "moderate" | "serious" | "critical";

/**
 * Runs axe (WCAG 2.1 A and AA). With `enforce`, serious and critical findings fail the test;
 * otherwise they are listed on the test report without failing it.
 */
export async function a11y(page: Page, { enforce = true, include }: { enforce?: boolean; include?: string } = {}) {
  // axe-core/playwright can resolve a different playwright-core than @playwright/test; the runtime API is the same.
  let builder = new AxeBuilder({ page: page as never }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]);
  if (include) builder = builder.include(include);
  const results = await builder.analyze();
  const bad = results.violations.filter((v) => (["serious", "critical"] as Impact[]).includes(v.impact as Impact));
  const summary = bad.map((v) => `${v.impact}: ${v.id} — ${v.help}\n${v.nodes.slice(0, 3).map((n) => `    ${n.target.join(" ")}`).join("\n")}`);
  if (enforce) {
    expect(summary, `Accessibility problems on ${page.url()}:\n${summary.join("\n")}`).toEqual([]);
  } else if (summary.length) {
    test.info().annotations.push({ type: "a11y (not enforced)", description: `${page.url()}\n${summary.join("\n")}` });
  }
}

/** The page never scrolls sideways. */
export async function expectNoHorizontalScroll(page: Page) {
  const { scroll, client } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(scroll, `page is ${scroll}px wide in a ${client}px window`).toBeLessThanOrEqual(client);
}

/** Saves a full-page screenshot for review (the workflow publishes these to the `e2e-shots` branch). */
export async function shot(page: Page, name: string) {
  fs.mkdirSync(shotsDir, { recursive: true });
  await page.screenshot({ path: path.join(shotsDir, `${name}.png`), fullPage: true });
}

/** Waits until the admin shell has finished its auth check and the page content is on screen. */
export async function adminReady(page: Page) {
  await expect(page.locator("#admin-main h1").first()).toBeVisible();
}

/** Answer a delete dialog's "type this code" prompt, then press its confirm button. */
export async function confirmDelete(page: Page, label: string) {
  const dialog = page.getByRole("dialog");
  const code = (await dialog.locator("label[for=confirm-code] strong").textContent()) ?? "";
  await dialog.getByLabel(/To confirm, type/).fill(code);
  await dialog.getByRole("button", { name: label }).click();
}
