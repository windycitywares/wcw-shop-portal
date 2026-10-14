// Turns Playwright's JSON results into GitHub annotations and a job summary, so a failure can be read
// from the check run without downloading artifacts.
import fs from "node:fs";

const file = new URL("../test-results/results.json", import.meta.url);
if (!fs.existsSync(file)) {
  console.log("::error title=E2E::No results file was produced. Check the earlier steps (server start-up, build).");
  process.exit(0);
}
const report = JSON.parse(fs.readFileSync(file, "utf8"));
const rows = [];
const failures = [];
const flaky = [];
const a11y = new Map();

function walk(suite, trail) {
  const here = suite.title && !suite.file ? [...trail, suite.title] : trail;
  for (const spec of suite.specs ?? []) {
    for (const t of spec.tests ?? []) {
      const name = [...here, spec.title].join(" › ");
      const last = t.results.at(-1);
      const status = t.status; // expected | unexpected | flaky | skipped
      rows.push({ name, status, ms: last?.duration ?? 0, file: spec.file });
      if (status === "unexpected") {
        const err = last?.error?.message ?? last?.errors?.[0]?.message ?? "failed";
        failures.push({ name, file: spec.file, err: err.replace(/\u001b\[[0-9;]*m/g, "").split("\n").slice(0, 14).join("\n") });
      }
      if (status === "flaky") flaky.push(name);
      for (const a of t.annotations ?? []) {
        if (a.type?.startsWith("a11y")) a11y.set(a.description, name);
      }
    }
  }
  for (const s of suite.suites ?? []) walk(s, here);
}
for (const s of report.suites ?? []) walk(s, []);

fs.mkdirSync(new URL("../shots/", import.meta.url), { recursive: true });
const esc = (s) => s.replace(/%/g, "%25").replace(/\r/g, "%0D").replace(/\n/g, "%0A");
const total = rows.length;
const failed = failures.length;
console.log(`E2E: ${total - failed - flaky.length} passed, ${flaky.length} flaky, ${failed} failed of ${total}`);

// Full detail goes to REPORT.md (published with the screenshots); the annotation stays short because
// GitHub truncates long messages.
const report_md = [
  `# E2E report: ${total - failed - flaky.length} passed, ${flaky.length} flaky, ${failed} failed of ${total}`,
  "",
  ...failures.map((f) => `## ✗ ${f.name}\n\`${f.file}\`\n\n\`\`\`\n${f.err}\n\`\`\`\n`),
  ...(flaky.length ? ["## Flaky (passed on retry)", ...flaky.map((n) => `- ${n}`), ""] : []),
  ...(a11y.size ? ["## Accessibility findings (not enforced)", ...[...a11y].map(([d, n]) => `### ${n}\n\`\`\`\n${d}\n\`\`\``)] : []),
].join("\n");
fs.writeFileSync(new URL("../shots/REPORT.md", import.meta.url), report_md);
if (failed) {
  const body = failures.map((f) => `✗ ${f.name} (${f.file}): ${f.err.split("\n").slice(0, 3).join(" | ").slice(0, 280)}`).join("\n");
  console.log(`::error title=E2E: ${failed} of ${total} tests failed::${esc(body.slice(0, 3500))}`);
}
if (flaky.length) console.log(`::warning title=E2E flaky tests::${esc(flaky.join("\n"))}`);
for (const [desc, name] of a11y) console.log(`::warning title=Accessibility (storefront): ${esc(name)}::${esc(desc.slice(0, 3000))}`);

if (process.env.GITHUB_STEP_SUMMARY) {
  const icon = { expected: "✅", unexpected: "❌", flaky: "⚠️", skipped: "⏭️" };
  const lines = [`### End-to-end tests: ${total - failed} of ${total} passed`, "", "| | Test | Time |", "|---|---|---|"];
  for (const r of rows) lines.push(`| ${icon[r.status] ?? r.status} | ${r.name.replace(/\|/g, "\\|")} | ${(r.ms / 1000).toFixed(1)}s |`);
  fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, lines.join("\n") + "\n");
}
