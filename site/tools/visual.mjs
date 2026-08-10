/**
 * Load every page in a real browser and measure it.
 *
 * `lint.tsx` reads the DOM; this reads the *rendering*. They catch different
 * things, and the difference is not academic — the bug that shipped was a note
 * rendered after a card that already filled its grid row, so it printed on top
 * of the row below. Nothing about that is visible in the markup. It is a
 * question about boxes, and only a browser knows where the boxes are.
 *
 *     npm run visual
 *
 * What it measures, per page and per width:
 *
 *   - overlapping text, by intersecting the bounding rects of every element
 *     that renders text and is not an ancestor of the other;
 *   - horizontal overflow of the document, which is a scrollbar the design
 *     never asked for;
 *   - text clipped by a fixed height;
 *   - controls smaller than the 44px hit target the design system requires;
 *   - sticky furniture occupying more than 15% of the viewport;
 *   - controls hidden inside a scroll container that gives no cue it scrolls.
 *
 * Screenshots land in `.visual/` so a person can look at what it measured.
 */

import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SHOTS = join(ROOT, ".visual");
const BASE = process.env.BASE_URL ?? "http://localhost:4173";

const ROUTES = [
  ["home", ""],
  ["how-it-works", "#/how-it-works"],
  ["scenarios", "#/scenarios"],
  ["for-agent-builders", "#/for-builders"],
  ["docs", "#/docs"],
  ["hosted", "#/hosted"],
  ["playground", "#/playground"],
  // The second design, by filename rather than by route: `vite preview` serves
  // dist/ without the host's rewrites, so /b resolves only in production and
  // /b.html resolves in both.
  ["b", "b.html"],
];

const WIDTHS = [390, 768, 1280, 1600];

let problems = 0;
// Worst sticky share seen, printed on success too. 14.9% against a >15 rule is
// a passing measurement with a tenth of a point of headroom, and a check that
// only speaks when it fails cannot tell you that.
let worstSticky = { where: "", share: 0 };
/*
 * A census of horizontal scrollers, printed on success.
 *
 * The hidden-controls check reports only failures, so a regression that
 * stops it seeing scrollers at all produces silence — and silence is
 * indistinguishable from a clean run. Counting what was inspected makes a
 * zero visible.
 */
let scrollersSeen = 0;
let scrollersCued = 0;
const report = (where, what) => {
  console.error(`  ✗ ${where}\n      ${what}`);
  problems += 1;
};

/**
 * Every element that paints its own text, with where it landed.
 *
 * Only leaves are considered: a paragraph and the span inside it always
 * "overlap", and reporting that would bury the one pair that matters.
 */
const MEASURE = `() => {
  const measured = [];
  for (const el of document.querySelectorAll("body *")) {
    const style = getComputedStyle(el);
    if (style.visibility === "hidden" || style.display === "none" || style.opacity === "0") continue;
    if (el.closest(".sr-only")) continue;

    const ownText = [...el.childNodes]
      .filter((n) => n.nodeType === 3)
      .map((n) => n.textContent.trim())
      .join(" ")
      .trim();
    if (!ownText) continue;

    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;

    measured.push({
      el,
      tag: el.tagName.toLowerCase(),
      text: ownText.slice(0, 70),
      x: r.x, y: r.y + window.scrollY, w: r.width, h: r.height,
      clipped: el.scrollHeight > el.clientHeight + 1 && style.overflowY === "hidden",
    });
  }

  /*
   * Overlap is decided here rather than in Node, because it needs
   * \`Node.contains\`. A paragraph that holds both raw text and an inline
   * <code> child paints text at both levels, and the parent's rect encloses
   * the child's by construction — every such pair intersects, and reporting
   * them buries the one pair that is a real collision.
   */
  const collisions = [];
  for (let i = 0; i < measured.length; i += 1) {
    for (let j = i + 1; j < measured.length; j += 1) {
      const a = measured[i], b = measured[j];
      if (a.el.contains(b.el) || b.el.contains(a.el)) continue;

      const ox = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
      const oy = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
      const area = ox * oy;
      if (area < 12) continue;
      collisions.push({ area: Math.round(area), a: a.text, b: b.text });
    }
  }

  const strip = ({ el, ...rest }) => rest;
  return {
    boxes: measured.map(strip),
    collisions,
    docWidth: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
    /*
     * A sticky element is charged against the viewport for the whole visit.
     * The header once wrapped to four rows and stood at 219px on a 390px
     * screen — 26% of it, permanently, with content ghosting through a
     * 95%-opaque background. Nothing overlapped and nothing overflowed, so
     * every other check here was happy.
     */
    sticky: [...document.querySelectorAll("body *")]
      .filter((el) => ["sticky", "fixed"].includes(getComputedStyle(el).position))
      .map((el) => ({
        tag: el.tagName.toLowerCase(),
        h: Math.round(el.getBoundingClientRect().height),
        share: Math.round((el.getBoundingClientRect().height / window.innerHeight) * 100),
      }))
      .filter((s) => s.h > 0),

    /*
     * Controls that must be reachable by a fingertip.
     *
     * A link inside a sentence is exempt, and not as a convenience: WCAG's
     * target-size rule carves out targets in a block of text, because the only
     * way to give one 44px is to break the line spacing around it. The test is
     * whether the parent paints text of its own besides the link — that is what
     * "inline in prose" means structurally. The earlier version exempted the
     * whole footer instead, which was the right answer for the wrong reason and
     * would have hidden a real footer button.
     */
    /*
     * Controls hidden inside a horizontal scroll, with nothing saying so.
     *
     * A scrolling row is a fine way to fit five destinations onto a phone, but
     * the only cue browsers give for free is a scrollbar — and iOS draws that
     * as an overlay that appears after you have already scrolled. Two of five
     * nav items were unreachable unless the visitor guessed to swipe a row that
     * did not look swipeable.
     *
     * So the rule is not "never hide": it is "if you hide, mark it".
     *
     * What counts as marked used to be *any* gradient anywhere on the element
     * or its ::after. That is far too loose to mean anything. A decorative
     * background — a blueprint grid, a tint, a sheen — would satisfy it while
     * telling the reader nothing, and this audit would then report "no layout
     * problems" for a page with unreachable controls. A confident false
     * negative is worse than no check, and worse here than anywhere, because
     * the comment above says in as many words that the failure is invisible by
     * nature.
     *
     * A cue now has to be both *declared* and *painted*:
     *
     *   - declared: \`data-scroll-cue\` on the scroller. The attribute alone
     *     cannot satisfy this, or anyone can silence the audit by typing it.
     *   - painted: a mask, or a horizontal fade to transparent. The paint
     *     alone cannot satisfy it either, or a decorative gradient counts as a
     *     promise the author never made.
     *
     * Vertical and radial gradients are deliberately not accepted: a fade at
     * the bottom of a box says nothing about content lost off its right edge.
     */
    hiddenControls: (() => {
      // Every backslash is doubled because this whole function is the body of
      // a template literal in Node, and a single one is eaten before Chrome
      // ever sees the source.
      const HORIZONTAL_FADE = /^(?:-webkit-)?linear-gradient\\((?:to (?:right|left)|90deg|270deg)\\b/;
      const TRANSPARENT = /transparent|rgba?\\([^)]*,\\s*0(?:\\.0+)?\\s*\\)/;
      const fades = (value) =>
        Boolean(value) &&
        value !== "none" &&
        HORIZONTAL_FADE.test(value) &&
        TRANSPARENT.test(value);

      const out = [];
      let scrollers = 0;
      let cued = 0;

      for (const el of document.querySelectorAll("body *")) {
        if (el.scrollWidth <= el.clientWidth + 1) continue;
        scrollers += 1;

        const style = getComputedStyle(el);
        const after = getComputedStyle(el, "::after");
        const marked =
          el.hasAttribute("data-scroll-cue") &&
          (style.maskImage !== "none" ||
            style.webkitMaskImage !== "none" ||
            fades(style.backgroundImage) ||
            (after.content !== "none" && fades(after.backgroundImage)));
        if (marked) cued += 1;

        const box = el.getBoundingClientRect();
        const lost = [...el.querySelectorAll("button, a[href], [role=button]")].filter((c) => {
          const r = c.getBoundingClientRect();
          return r.width > 0 && (r.right > box.right + 1 || r.left < box.left - 1);
        });
        if (lost.length === 0) continue;

        if (!marked) {
          out.push({
            tag: el.tagName.toLowerCase(),
            hidden: Math.round(el.scrollWidth - el.clientWidth),
            labels: lost.map((c) => c.textContent.trim().slice(0, 30)),
          });
        }
      }
      return { found: out, scrollers, cued };
    })(),

    smallTargets: [...document.querySelectorAll("button, a[href], [role=button]")]
      .filter((el) => {
        if (el.closest(".sr-only")) return false;
        const parent = el.parentElement;
        if (!parent) return true;
        const siblingText = [...parent.childNodes]
          .filter((n) => n.nodeType === 3)
          .map((n) => n.textContent.trim())
          .join("");
        return siblingText.length === 0;
      })
      .map((el) => ({ el, r: el.getBoundingClientRect() }))
      .filter(({ r }) => r.height > 0 && r.height < 44)
      .map(({ el, r }) => ({ text: (el.textContent || el.getAttribute("aria-label") || "?").trim().slice(0, 40), h: Math.round(r.height) })),
  };
}`;

mkdirSync(SHOTS, { recursive: true });

/*
 * Drive the Chrome already installed on this machine rather than Playwright's
 * own build. It saves a ~140MB download for a check that only needs a layout
 * engine, and it measures the browser people actually use. Set
 * `BEACON_BROWSER=bundled` to use Playwright's Chromium instead.
 */
const browser = await chromium.launch(
  process.env.BEACON_BROWSER === "bundled" ? {} : { channel: "chrome" },
);

for (const [name, hash] of ROUTES) {
  for (const width of WIDTHS) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    const where = `${name} @ ${width}px`;

    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

    await page.goto(`${BASE}/${hash}`, { waitUntil: "networkidle" });
    // The timeline streams; let it settle so the measurement is of a real state.
    await page.waitForTimeout(400);

    // Invoked, not just evaluated: a string passed to `evaluate` is treated as
    // an expression, and a bare arrow function is an expression whose value is
    // the function itself.
    const { boxes, collisions, docWidth, viewport, smallTargets, sticky, hiddenControls } = await page.evaluate(`(${MEASURE})()`);

    for (const message of errors) report(where, `console error: ${message}`);

    if (docWidth > viewport + 1) {
      report(where, `document is ${docWidth - viewport}px wider than the viewport`);
    }

    for (const box of boxes.filter((b) => b.clipped)) {
      report(where, `text clipped by a fixed height: "${box.text}"`);
    }

    for (const bar of sticky) {
      if (bar.share > worstSticky.share) worstSticky = { where, share: bar.share };
    }

    // 15% is generous for a header. The one that shipped was 26%.
    for (const bar of sticky.filter((s) => s.share > 15)) {
      report(where, `sticky <${bar.tag}> is ${bar.h}px — ${bar.share}% of the viewport`);
    }

    scrollersSeen += hiddenControls.scrollers;
    scrollersCued += hiddenControls.cued;

    for (const scroller of hiddenControls.found) {
      report(
        where,
        `<${scroller.tag}> hides ${scroller.hidden}px of controls with no scroll cue: ${scroller.labels.join(", ")}`,
      );
    }

    for (const target of smallTargets) {
      report(where, `hit target ${target.h}px, under the 44px the design system requires: "${target.text}"`);
    }

    for (const hit of collisions) {
      report(where, `text overlaps text (${hit.area}px²):\n        "${hit.a}"\n        "${hit.b}"`);
    }

    await page.screenshot({
      path: join(SHOTS, `${name}-${width}.png`),
      fullPage: width === 1280,
    });
    await page.close();
  }
}

await browser.close();

console.log();
if (problems > 0) {
  console.error(`${problems} problem(s) found. Screenshots in site/.visual/`);
  process.exit(1);
}
console.log(`No layout problems found across ${ROUTES.length} pages × ${WIDTHS.length} widths.`);
console.log(`Worst sticky furniture: ${worstSticky.share}% of the viewport (${worstSticky.where}), against a 15% limit.`);
console.log(`Horizontal scrollers: ${scrollersSeen} inspected, ${scrollersCued} carrying a scroll cue.`);
console.log(`Screenshots in site/.visual/`);
