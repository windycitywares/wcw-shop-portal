import fs from "node:fs";
import path from "node:path";

/** Signs in once through the API and saves the browser state, so tests don't have to log in each time. */
export default async function globalSetup() {
  const api = process.env.E2E_API_URL || "http://localhost:8000/api/v1";
  const base = process.env.E2E_BASE_URL || "http://localhost:3000";
  const email = process.env.ADMIN_EMAIL;
  const password = process.env.ADMIN_PASSWORD;
  if (!email || !password) throw new Error("Set ADMIN_EMAIL and ADMIN_PASSWORD (the seeded admin) to run the e2e tests.");

  const res = await fetch(`${api}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
  if (!res.ok) throw new Error(`Admin login failed (${res.status}): ${await res.text()}`);
  const { access_token } = (await res.json()) as { access_token: string };

  const dir = path.join(__dirname, ".auth");
  fs.mkdirSync(dir, { recursive: true });
  const origin = new URL(base).origin;
  fs.writeFileSync(
    path.join(dir, "admin.json"),
    JSON.stringify({ cookies: [], origins: [{ origin, localStorage: [{ name: "wcw-token", value: access_token }] }] }),
  );
  fs.writeFileSync(path.join(dir, "token.txt"), access_token);
}
