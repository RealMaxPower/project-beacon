/**
 * Serve `dist/` the way `vercel.json` says the host will, and drive it.
 *
 * A Content-Security-Policy is the one piece of configuration that cannot be
 * reviewed by reading it. `style-src 'self'` looks like it forbids the inline
 * `style={{ width }}` this site uses on three elements — it does not, because
 * React sets those through the CSSOM rather than as markup, and CSP governs
 * markup. Getting that wrong in either direction is invisible until a visitor
 * loads the page: too strict and the bars do not render, too loose and the
 * header is decorative.
 *
 * So this applies the real headers from the real config file, walks every
 * page, and fails on any CSP violation or console error. `vite preview` cannot
 * do it — it serves no custom headers, which is exactly the part under test.
 *
 *     node tools/headers.mjs
 */

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, extname } from "node:path";
import { chromium } from "playwright";

const DIST = "dist";
const config = JSON.parse(await readFile("vercel.json", "utf8"));

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".json": "application/json",
};

/** The headers vercel.json declares for a path, in its own order. */
function headersFor(pathname) {
  const out = {};
  for (const rule of config.headers ?? []) {
    const pattern = new RegExp(`^${rule.source.replace(/\/\(\.\*\)$/, "/.*")}$`);
    if (pattern.test(pathname)) {
      for (const { key, value } of rule.headers) out[key] = value;
    }
  }
  return out;
}

const server = createServer(async (req, res) => {
  const pathname = new URL(req.url, "http://x").pathname;
  // Filesystem first, then the catch-all rewrite — the order Vercel uses.
  const candidate = join(DIST, pathname);
  const file = existsSync(candidate) && extname(candidate) ? candidate : join(DIST, "index.html");
  const served = existsSync(candidate) && extname(candidate) ? pathname : "/";

  const body = await readFile(file);
  res.writeHead(200, {
    "Content-Type": TYPES[extname(file)] ?? "application/octet-stream",
    ...headersFor(served),
  });
  res.end(body);
});

await new Promise((r) => server.listen(0, r));
const base = `http://localhost:${server.address().port}`;
console.log(`serving dist/ with vercel.json headers on ${base}\n`);

const browser = await chromium.launch({ channel: "chrome" });
const page = await browser.newPage();

const violations = [];
page.on("console", (m) => {
  const t = m.text();
  if (m.type() === "error" || /Content Security Policy/i.test(t)) violations.push(t);
});
page.on("pageerror", (e) => violations.push(`pageerror: ${e.message}`));

const ROUTES = [
  "/",
  "/#/how-it-works",
  "/#/scenarios",
  "/#/for-builders",
  "/#/docs",
  "/#/hosted",
  "/#/playground",
  "/#/playground/inbox-briefing-draft-only",
];

let failures = 0;
for (const route of ROUTES) {
  violations.length = 0;
  await page.goto(base + route, { waitUntil: "networkidle" });
  await page.waitForTimeout(250);
  const painted = await page.locator("#root").innerText();
  const ok = painted.trim().length > 200 && violations.length === 0;
  if (!ok) failures += 1;
  console.log(`  ${ok ? "ok  " : "FAIL"} ${route.padEnd(42)} ${painted.trim().length} chars rendered`);
  for (const v of violations.slice(0, 3)) console.log(`         ${v.slice(0, 160)}`);
}

// The one place an inline style is load-bearing: the pass-rate bars are sized
// by `style={{ width }}`. A CSP that blocked them would leave a bar at zero
// width and nothing in the console, so it is asserted rather than eyeballed.
await page.goto(`${base}/`, { waitUntil: "networkidle" });
const widths = await page.evaluate(() =>
  [...document.querySelectorAll("[style*='width']")].map((el) => el.style.width),
);
const sized = widths.filter((w) => w && w !== "0%" && w !== "0px");
console.log(`\n  ${sized.length > 0 ? "ok  " : "FAIL"} inline widths survive style-src 'self': ${JSON.stringify(widths)}`);
if (sized.length === 0) failures += 1;

/*
 * A download uses a blob: URL. Nothing in the policy should stop it.
 *
 * Wrapped, because every step here is a click on something the previous step
 * had to render. Under a policy that blocks the bundle there is nothing to
 * click, and an unguarded walk dies on a locator timeout — turning a legible
 * "the CSP is too strict" into a stack trace forty lines from the cause.
 */
violations.length = 0;
async function walkToVerdict() {
  await page.goto(`${base}/#/playground/inbox-briefing-draft-only`, { waitUntil: "networkidle" });
  await page.locator("button").filter({ hasText: /level \d/ }).first().click({ timeout: 3000 });
  await page.waitForTimeout(200);
  await page.locator("button", { hasText: "Run it" }).first().click({ timeout: 3000 });
  await page.waitForTimeout(200);
  const skip = page.locator("button", { hasText: /Skip to end/i }).first();
  if (await skip.count()) { await skip.click(); await page.waitForTimeout(500); }
  const verdict = page.locator("button", { hasText: /See the verdict/i }).first();
  if (await verdict.count()) { await verdict.click(); await page.waitForTimeout(400); }
  return true;
}
const reachedVerdict = await walkToVerdict().catch((e) => {
  violations.push(`could not reach the verdict screen: ${e.message.split("\n")[0]}`);
  return false;
});
// The control is labelled "Download"; the file it fetches is named on the card
// around it. Matching the button by the filename finds nothing.
const dl = page.locator("article", { hasText: "evidence.json" }).getByRole("button", { name: "Download" }).first();
let downloaded = "not reached";
if (reachedVerdict && (await dl.count())) {
  const wait = page.waitForEvent("download", { timeout: 4000 }).catch(() => null);
  await dl.click();
  const got = await wait;
  downloaded = got ? got.suggestedFilename() : "no download fired";
}
const dlOk = downloaded.endsWith(".json") && violations.length === 0;
if (!dlOk) failures += 1;
console.log(`  ${dlOk ? "ok  " : "FAIL"} blob: download under the policy: ${downloaded}`);
for (const v of violations.slice(0, 3)) console.log(`         ${v.slice(0, 160)}`);

// And the headers themselves actually reached the wire.
const res = await page.request.get(`${base}/`);
const got = res.headers();
const required = [
  "content-security-policy",
  "x-content-type-options",
  "referrer-policy",
  "permissions-policy",
  "strict-transport-security",
];
const missing = required.filter((h) => !got[h]);
if (missing.length) failures += 1;
console.log(`  ${missing.length ? "FAIL" : "ok  "} headers present on /: ${missing.length ? `missing ${missing.join(", ")}` : required.length + " of " + required.length}`);

const scriptName = (await page.evaluate(() => [...document.scripts].map((s) => s.src.split("/assets/")[1]))).filter(Boolean)[0];
const asset = scriptName ? await page.request.get(`${base}/assets/${scriptName}`) : null;
const cache = asset?.headers()["cache-control"] ?? "";
const cacheOk = cache.includes("immutable");
if (!cacheOk) failures += 1;
console.log(`  ${cacheOk ? "ok  " : "FAIL"} hashed assets are immutable: ${cache || "(none)"}`);

await browser.close();
server.close();
console.log(failures ? `\n${failures} check(s) failed.` : "\nThe policy holds on every page.");
process.exit(failures ? 1 : 0);
