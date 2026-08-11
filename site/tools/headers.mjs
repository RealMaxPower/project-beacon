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

/**
 * The document a path resolves to, following the config's own rewrites.
 *
 * This used to answer `index.html` for every extensionless path, which was
 * correct only while the site had one page. The moment a second entry exists,
 * a request for its URL would be served the *first* page, painted more than
 * the check's minimum, and reported as passing — the audit would be confirming
 * a policy on a document it had never loaded. A tool whose job is to prove the
 * real headers hold has to resolve paths the way the real host does, so it
 * reads the same `rewrites` array it is testing.
 */
function documentFor(pathname) {
  for (const rule of config.rewrites ?? []) {
    if (!new RegExp(`^${rule.source}$`).test(pathname)) continue;
    const target = rule.destination === "/" ? "/index.html" : rule.destination;
    const file = join(DIST, extname(target) ? target : `${target}.html`);
    if (existsSync(file)) return { file, served: rule.destination };
  }
  return { file: join(DIST, "index.html"), served: "/" };
}

const server = createServer(async (req, res) => {
  const pathname = new URL(req.url, "http://x").pathname;
  // Filesystem first, then the rewrites — the order Vercel uses.
  const candidate = join(DIST, pathname);
  const onDisk = existsSync(candidate) && extname(candidate);
  const { file, served } = onDisk ? { file: candidate, served: pathname } : documentFor(pathname);

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
  // The licensing and privacy page. Its claims about what this site collects
  // are claims about this policy, so it is the one page where a violation
  // would make the prose false rather than merely break a feature.
  "/#/legal",
  "/#/playground",
  "/#/playground/inbox-briefing-draft-only",
  // The second design. It is a separate document, so it inherits the policy
  // but proves nothing about it until it is actually loaded — which is what
  // the rewrite-aware resolver above exists to make true.
  "/b",
  // The shared playground under the second design's shell. Same document and
  // so the same policy, but not the same code path: this route is where
  // `crypto.subtle` and the blob download run, and a policy that held on the
  // marketing page says nothing about the screen that actually uses them.
  "/b#/playground",
  "/b#/docs",
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

/*
 * The second design is the second design.
 *
 * "More than 200 characters painted" is satisfied just as well by the first
 * site, which is precisely what this harness used to serve for /b — so the
 * route check above would have gone green on the very bug that made it
 * meaningless. Assert the document by something only it renders.
 */
await page.goto(`${base}/b`, { waitUntil: "networkidle" });
const bMarkers = await page.evaluate(() => ({
  heading: document.querySelector("h1")?.textContent ?? "",
  font: getComputedStyle(document.querySelector("h1") ?? document.body).fontFamily,
}));
const isB = bMarkers.heading.includes("defend") && /Archivo/i.test(bMarkers.font);
if (!isB) failures += 1;
console.log(
  `  ${isB ? "ok  " : "FAIL"} /b served the second design: ${JSON.stringify(bMarkers.heading)} in ${bMarkers.font.split(",")[0]}`,
);

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
 * The alias block, checked where it can actually be wrong.
 *
 * The shared playground is styled with the first design's utility names, and
 * `tokens-b.css` declares those names against this design's palette. Nothing in
 * the markup can show whether that worked: the class is `text-text-muted`
 * either way, and had the alias been missing the rule would simply not exist
 * and the text would inherit. So this asks the browser what colour it ended up
 * and compares it to the token — which is the only form of this check capable
 * of failing.
 */
await page.goto(`${base}/b#/playground`, { waitUntil: "networkidle" });
const paint = await page.evaluate(() => {
  const el = document.querySelector(".text-text-muted");
  if (!el) return null;
  const probe = document.createElement("span");
  probe.style.color = getComputedStyle(document.documentElement).getPropertyValue("--b-muted");
  document.body.appendChild(probe);
  const want = getComputedStyle(probe).color;
  probe.remove();
  return { got: getComputedStyle(el).color, want };
});
if (!paint) {
  console.log("  FAIL no .text-text-muted on /b#/playground — the shared playground did not render");
  failures += 1;
} else if (paint.got !== paint.want) {
  console.log(`  FAIL the playground kept another palette: ${paint.got} is not --b-muted ${paint.want}`);
  failures += 1;
} else {
  console.log(`  ok   the shared playground repaints from --b-muted: ${paint.got}`);
}

/*
 * And that it wears this design's type and accent, not the first design's.
 *
 * These two are scoped rules rather than aliases, hung off an attribute set in
 * `SiteB.tsx`. Delete the attribute and nothing breaks, nothing throws, and the
 * screen quietly reverts to the other site's voice — headings back to Inter and
 * every primary button back to an inverted white chip. That is precisely the
 * failure a screenshot review stops catching once the page is familiar.
 */
const brand = await page.evaluate(() => {
  const h = document.querySelector("[data-shared-screen] h1");
  const btn = document.querySelector("[data-shared-screen] .bg-text");
  const probe = document.createElement("span");
  probe.style.color = getComputedStyle(document.documentElement).getPropertyValue("--b-src");
  document.body.appendChild(probe);
  const src = getComputedStyle(probe).color;
  probe.remove();
  return {
    face: h ? getComputedStyle(h).fontFamily : null,
    fill: btn ? getComputedStyle(btn).backgroundColor : null,
    src,
  };
});
if (!brand.face || !brand.face.includes("Archivo")) {
  console.log(`  FAIL the shared playground's heading is not in Archivo: ${brand.face}`);
  failures += 1;
} else if (brand.fill !== brand.src) {
  console.log(`  FAIL its primary action is not --b-src: ${brand.fill} vs ${brand.src}`);
  failures += 1;
} else {
  console.log(`  ok   it wears this design's type and accent: Archivo, ${brand.fill}`);
}

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
