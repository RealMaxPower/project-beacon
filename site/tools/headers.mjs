/**
 * Drive every page under the real headers, and fail on anything the policy
 * breaks.
 *
 * A Content-Security-Policy is the one piece of configuration that cannot be
 * reviewed by reading it. `style-src 'self'` looks like it forbids the inline
 * `style={{ width }}` this site uses in nine components — and for a long time
 * it did not, because React writes styles through the CSSOM and CSP governs
 * markup. Prerendering turned those same declarations into attributes, this
 * walk went red on the first run, and the answer was to lift them into a
 * generated stylesheet rather than to weaken the policy. That is the shape of
 * the thing: too strict and the page breaks silently, too loose and the header
 * is decorative, and neither is visible without loading the page.
 *
 * The server is `tools/serve.mjs`, shared with the layout audit, because the
 * two used to disagree about how this site is served and only one of them was
 * right.
 *
 *     node tools/headers.mjs
 */

import { chromium } from "playwright";
import { startStaticServer } from "./serve.mjs";

const { server, base } = await startStaticServer();
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
  "/docs",
  "/legal",
  "/playground",
  "/playground/inbox-briefing-draft-only",
  "/#case",
];

/*
 * The two files the SPA catch-all used to swallow.
 *
 * Both returned HTTP 200 and `text/html` in production, because every path
 * rewrote to the landing page — a robots file that is a web page is worse than
 * a missing one, since a crawler parses it and finds no rules. They are real
 * files now, and this is the check that says so: the status, the content type,
 * and a line only the real file contains.
 */
const FILES = [
  ["/robots.txt", "text/plain", "Sitemap: "],
  ["/sitemap.xml", "application/xml", "<urlset"],
  ["/llms.txt", "text/plain", "## Pages"],
  // The markdown twins. Served to anyone who asks, which is the difference
  // between a format and an edition for machines: no User-Agent is consulted
  // anywhere, and this URL is as open to a reader as to a crawler.
  ["/index.md", "text/markdown", "canonical: "],
  ["/docs.md", "text/markdown", "canonical: "],
  // The legacy icon paths, each of which was a 404. Modern browsers take the
  // SVG; crawlers, feed readers and iOS home-screen saves ask for these names.
  ["/favicon.ico", "image/", "PNG"],
  ["/apple-touch-icon.png", "image/png", "PNG"],
  ["/site.webmanifest", "application/manifest+json", "Project Beacon"],
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
 * /b redirects rather than resolving.
 *
 * It is where this design lived while it was reviewed against the one it
 * replaced, so links shared during that fortnight still exist. It was a
 * rewrite, which served the landing document at a URL the client router did
 * not recognise — so the page rendered not-found over its own content. A
 * permanent redirect says the one true thing: that address moved.
 */
const legacy = await page.request.get(`${base}/b`, { maxRedirects: 0 });
const legacyOk = legacy.status() === 308 && legacy.headers()["location"] === "/";
if (!legacyOk) failures += 1;
console.log(
  `  ${legacyOk ? "ok  " : "FAIL"} /b redirects to /: ${legacy.status()} ${legacy.headers()["location"] ?? ""}`,
);

/*
 * The pass-rate bars are sized by data, and a policy that stopped them would
 * leave every bar at zero width with nothing in the console.
 *
 * This used to read `el.style.width` — the inline attribute — which was the
 * mechanism rather than the property. The mechanism changed: the prerender
 * step lifts those declarations into `/prerender.css` so `style-src 'self'`
 * can stay, and the check went red while every bar on the page was correct.
 * It now measures what it always meant to: the width a bar actually has.
 */
const widthProbe = `${base}/playground`;
await page.goto(widthProbe, { waitUntil: "networkidle" });
const bars = await page.evaluate(() =>
  [...document.querySelectorAll("[data-bs], [style*='width']")]
    .filter((el) => getComputedStyle(el).width !== "auto")
    .map((el) => Math.round(el.getBoundingClientRect().width)),
);
const sized = bars.filter((w) => w > 0);
console.log(
  `\n  ${sized.length > 0 ? "ok  " : "FAIL"} data-driven widths render under style-src 'self' on ${widthProbe}: ${sized.length} of ${bars.length} sized`,
);
if (sized.length === 0) failures += 1;

/*
 * A lifted declaration a stylesheet could still overwrite.
 *
 * The check above probes a `width`, which nothing else on this site sets, so
 * it passed while a different lifted property was being clobbered: the
 * pipeline's per-stage `animation-delay` moved into `/prerender.css`, and
 * `.b-stage` set `animation:` as a shorthand — same specificity, later in
 * source order, and a shorthand resets every longhand it omits. Six stages
 * revealed at once. The animation ran, the fade was right, and the sequence it
 * exists to show was gone, with nothing wrong in the DOM to find.
 *
 * So this probes a property that a shorthand *can* reset, which is the case
 * the other probe cannot see.
 */
await page.goto(`${base}/`, { waitUntil: "networkidle" });
const staged = await page.evaluate(() =>
  [...document.querySelectorAll(".b-stage")].map((el) => getComputedStyle(el).animationDelay),
);
const staggered = new Set(staged).size > 1;
if (!staggered) failures += 1;
console.log(
  `  ${staggered ? "ok  " : "FAIL"} lifted animation-delay survives the stylesheet: ${new Set(staged).size} distinct of ${staged.length}`,
);

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
await page.goto(`${base}/playground`, { waitUntil: "networkidle" });
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
  console.log("  FAIL no .text-text-muted on /playground — the shared playground did not render");
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
  await page.goto(`${base}/playground/inbox-briefing-draft-only`, { waitUntil: "networkidle" });
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

for (const [path, type, marker] of FILES) {
  const response = await page.request.get(base + path);
  const body = await response.text();
  const contentType = response.headers()["content-type"] ?? "";
  const ok = response.status() === 200 && contentType.startsWith(type) && body.includes(marker);
  if (!ok) failures += 1;
  console.log(
    `  ${ok ? "ok  " : "FAIL"} ${path.padEnd(42)} ${response.status()} ${contentType.split(";")[0]}`,
  );
}

/*
 * An unknown path must be a 404, not the landing page with a 200 on it.
 *
 * That is what the catch-all rewrite did, and it is the reason to check rather
 * than assume: a host answering every URL with the same page and a success
 * status invites a crawler to index it under all of them.
 */
const unknownPath = await page.request.get(`${base}/no-such-page`);
const missingOk =
  unknownPath.status() === 404 && (await unknownPath.text()).includes("noindex");
if (!missingOk) failures += 1;
console.log(
  `  ${missingOk ? "ok  " : "FAIL"} ${"/no-such-page".padEnd(42)} ${unknownPath.status()}, noindex`,
);

await browser.close();
server.close();
console.log(failures ? `\n${failures} check(s) failed.` : "\nThe policy holds on every page.");
process.exit(failures ? 1 : 0);
